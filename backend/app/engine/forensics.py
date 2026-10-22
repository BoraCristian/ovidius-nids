"""Forensics helpers: persist a mini-PCAP per alert so the analyst can
investigate the packets that triggered the detection."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .packet import Packet


def write_packet_log(alert_id: int, packets: list[Packet], pcap_dir: Path) -> Path:
    """Serialise a small ring-buffer of packets around an alert as JSONL.

    We use JSONL (not libpcap format) so the UI can render it directly and
    the forensics module has no dependency on Wireshark/tshark. When Scapy
    is available and live sniffing is used, the caller can additionally
    write a proper PCAP using scapy.wrpcap().
    """
    pcap_dir.mkdir(parents=True, exist_ok=True)
    path = pcap_dir / f"alert_{alert_id}_{int(datetime.now(timezone.utc).timestamp())}.jsonl"
    with path.open("w", encoding="utf-8") as fp:
        for p in packets:
            fp.write(json.dumps({
                "ts": p.ts.isoformat(),
                "protocol": p.protocol,
                "src_ip": p.src_ip,
                "src_port": p.src_port,
                "dst_ip": p.dst_ip,
                "dst_port": p.dst_port,
                "length": p.length,
                "flags": p.flags,
                "payload_preview": p.payload_text()[:256],
            }) + "\n")
    return path
