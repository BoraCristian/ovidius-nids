"""Signature-based detection.

Rules are stored as JSON-serialisable dicts (portable, DB-friendly) instead
of raw Snort syntax. This keeps the rule editor in the UI clean while still
supporting the common detection primitives.

Match specification
-------------------
match = {
    "protocol":   "tcp" | "udp" | "icmp" | "any",
    "src_ip":     "any" | "10.0.0.0/8",
    "src_port":   "any" | 443 | "80-8080",
    "dst_ip":     "any" | "192.168.1.1",
    "dst_port":   "any" | 22,
    "flags":      ["S"] | ["S","A"]       # match TCP flags set
    "content":    "admin"                 # substring in payload (case-insensitive)
    "regex":      "(?i)select .+ from"
    "min_length": 1400
    "threshold":  {"count": 20, "seconds": 10, "track": "src_ip"}
}
"""
from __future__ import annotations

import ipaddress
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable

from .packet import Packet


# ---------- primitive matchers ---------------------------------------------------

def _match_ip(spec: str | None, ip: str) -> bool:
    if not spec or spec == "any":
        return True
    try:
        if "/" in spec:
            return ipaddress.ip_address(ip) in ipaddress.ip_network(spec, strict=False)
        return spec == ip
    except ValueError:
        return False


def _match_port(spec: Any, port: int) -> bool:
    if spec in (None, "any", "", 0):
        return True
    if isinstance(spec, int):
        return spec == port
    if isinstance(spec, str):
        if "-" in spec:
            a, b = spec.split("-", 1)
            try:
                return int(a) <= port <= int(b)
            except ValueError:
                return False
        try:
            return int(spec) == port
        except ValueError:
            return False
    if isinstance(spec, (list, tuple)):
        return port in spec
    return False


def _match_flags(spec: list[str] | None, flags: str) -> bool:
    if not spec:
        return True
    wanted = {f.upper() for f in spec}
    have = {f.strip().upper() for f in flags.split(",") if f.strip()}
    return wanted.issubset(have)


def _match_content(spec: str | None, payload: bytes) -> bool:
    if not spec:
        return True
    return spec.lower().encode() in payload.lower()


def _match_regex(spec: str | None, payload: bytes) -> bool:
    if not spec:
        return True
    try:
        text = payload.decode("utf-8", errors="replace")
    except Exception:
        return False
    return bool(re.search(spec, text))


# ---------- thresholding (e.g. "20 SYNs in 10s") --------------------------------

class _ThresholdTracker:
    """Tracks per-rule sliding-window counters."""
    def __init__(self) -> None:
        # key = (rule_id, track_value) -> deque[timestamps]
        self._events: dict[tuple[int, str], deque[float]] = defaultdict(deque)

    def hit(self, rule_id: int, track_key: str, count: int, seconds: float) -> bool:
        now = time.monotonic()
        q = self._events[(rule_id, track_key)]
        q.append(now)
        # drop anything outside the window
        cutoff = now - seconds
        while q and q[0] < cutoff:
            q.popleft()
        return len(q) >= count


# ---------- rule + engine -------------------------------------------------------

@dataclass
class CompiledRule:
    id: int
    name: str
    category: str
    severity: str
    action: str
    match: dict[str, Any]
    description: str | None = None


class SignatureEngine:
    """Evaluate packets against a live, hot-reloadable rule set."""

    def __init__(self) -> None:
        self._rules: list[CompiledRule] = []
        self._threshold = _ThresholdTracker()

    # -------- rule management --------
    def load(self, rules: Iterable[CompiledRule]) -> None:
        self._rules = [r for r in rules]

    def replace_rule(self, rule: CompiledRule) -> None:
        self._rules = [r for r in self._rules if r.id != rule.id] + [rule]

    def remove_rule(self, rule_id: int) -> None:
        self._rules = [r for r in self._rules if r.id != rule_id]

    @property
    def count(self) -> int:
        return len(self._rules)

    # -------- evaluation --------
    def evaluate(self, pkt: Packet) -> list[dict[str, Any]]:
        """Return a list of alert dicts produced by the packet."""
        alerts: list[dict[str, Any]] = []
        for rule in self._rules:
            m = rule.match or {}
            proto = m.get("protocol", "any")
            if proto and proto != "any" and proto.lower() != pkt.protocol.lower():
                continue
            if not _match_ip(m.get("src_ip"), pkt.src_ip):
                continue
            if not _match_ip(m.get("dst_ip"), pkt.dst_ip):
                continue
            if not _match_port(m.get("src_port"), pkt.src_port):
                continue
            if not _match_port(m.get("dst_port"), pkt.dst_port):
                continue
            if not _match_flags(m.get("flags"), pkt.flags):
                continue
            if not _match_content(m.get("content"), pkt.payload):
                continue
            if not _match_regex(m.get("regex"), pkt.payload):
                continue
            min_len = m.get("min_length")
            if isinstance(min_len, int) and pkt.length < min_len:
                continue

            # Optional threshold: e.g. {"count": 20, "seconds": 10, "track": "src_ip"}
            threshold = m.get("threshold")
            if isinstance(threshold, dict):
                track_field = threshold.get("track", "src_ip")
                track_value = str(getattr(pkt, track_field, pkt.src_ip))
                count = int(threshold.get("count", 10))
                seconds = float(threshold.get("seconds", 10))
                if not self._threshold.hit(rule.id, track_value, count, seconds):
                    continue

            alerts.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "severity": rule.severity,
                "category": rule.category,
                "detection_method": "signature",
                "message": f"{rule.name}: {rule.description or 'match'}",
                "src_ip": pkt.src_ip,
                "src_port": pkt.src_port,
                "dst_ip": pkt.dst_ip,
                "dst_port": pkt.dst_port,
                "protocol": pkt.protocol,
                "raw_payload": pkt.payload_text()[:512] or None,
                "extra": {"flags": pkt.flags, "length": pkt.length},
            })
        return alerts


# Singleton used by the app
engine = SignatureEngine()
