"""Lightweight in-memory representation of a network packet.

We don't depend on Wireshark or tshark — every field we consume is extracted
ourselves (from Scapy in live mode, or synthesised in simulation mode)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Packet:
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    protocol: str = "TCP"
    src_ip: str = "0.0.0.0"
    src_port: int = 0
    dst_ip: str = "0.0.0.0"
    dst_port: int = 0
    length: int = 0
    flags: str = ""                              # e.g. "SYN", "ACK", "SYN,ACK"
    payload: bytes = b""
    meta: dict[str, Any] = field(default_factory=dict)

    def payload_text(self) -> str:
        try:
            return self.payload.decode("utf-8", errors="replace")
        except Exception:
            return ""
