"""Small utilities shared by several test modules."""
from __future__ import annotations

import ipaddress

# RFC 5737 ranges reserved for documentation; the simulator's attackers live here.
DOCUMENTATION_NETS = [
    ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
]


def is_documentation_ip(ip: str) -> bool:
    return any(ipaddress.ip_address(ip) in net for net in DOCUMENTATION_NETS)


class FakeClock:
    """Stand-in for the `time` module so time-dependent code is deterministic."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now


async def noop_handler(_pkt) -> None:
    """Packet handler for a TrafficSimulator used only for its packet factories."""
