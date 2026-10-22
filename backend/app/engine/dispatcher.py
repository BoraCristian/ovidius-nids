"""Central dispatcher.

Every packet ingested by the sniffer (or the simulator) flows through here:

    Packet  ─►  SignatureEngine.evaluate()  ─┐
                                             ├─►  dedup / merge  ─►  DB + pcap + WebSocket
                MLDetector.score()          ─┘

The `Dispatcher` object is also the source of truth for the live-metrics that
the dashboard reads (total packets, pps, alert count)."""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.event import TrafficEvent
from app.models.pcap import PcapRecord

from .bus import alert_bus, traffic_bus
from .forensics import write_packet_log
from .ml_detector import detector
from .packet import Packet
from .signatures import engine

# --------------------------------------------------------------------------- #
# Tuning constants                                                             #
# --------------------------------------------------------------------------- #
RING_SIZE          = 200       # recent packets kept for forensic snapshots
SNAPSHOT_TAIL      = 50        # packets to persist per alert
TRAFFIC_SAMPLE     = 5         # store 1 in N packets as TrafficEvent
PPS_WINDOW_SEC     = 1.0
ML_ALERT_THRESHOLD = 0.8
ML_HIGH_THRESHOLD  = 0.9


class Dispatcher:
    def __init__(self, pcap_dir, enable_ml: bool = True) -> None:
        self.pcap_dir = pcap_dir
        self.enable_ml = enable_ml

        self._pkt_count   = 0
        self._alert_count = 0
        self._ring: deque[Packet] = deque(maxlen=RING_SIZE)

        # Sliding-window pps tracker
        self._last_pps_ts    = time.monotonic()
        self._pps_counter    = 0
        self._last_pps_value = 0.0

    # ------- public metrics -------
    @property
    def packets(self) -> int:   return self._pkt_count
    @property
    def alerts(self) -> int:    return self._alert_count
    def     pps(self) -> float: return self._last_pps_value

    # --------------------------------------------------------------------- #
    # Main entry point                                                       #
    # --------------------------------------------------------------------- #
    async def handle(self, pkt: Packet) -> None:
        self._pkt_count += 1
        self._ring.append(pkt)
        self._tick_pps()

        await self._publish_traffic(pkt)
        await self._maybe_persist_event(pkt)

        alerts = self._evaluate(pkt)
        if alerts:
            await self._persist_and_broadcast(alerts)

    # --------------------------------------------------------------------- #
    # Detection                                                              #
    # --------------------------------------------------------------------- #
    def _evaluate(self, pkt: Packet) -> list[dict[str, Any]]:
        """Run both engines and merge their verdicts into alert candidates."""
        signature_hits: list[dict[str, Any]] = list(engine.evaluate(pkt))

        ml_label, ml_score = 0, 0.0
        if self.enable_ml and detector.is_active():
            ml_label, ml_score = detector.score(pkt)

        # ML-only alert: only when no signature matched, score is high enough
        if ml_label == 1 and ml_score >= ML_ALERT_THRESHOLD and not signature_hits:
            return [self._ml_candidate(pkt, ml_score)]

        # Hybrid: signature matched AND the ML classifier agreed
        if signature_hits and ml_label == 1:
            for h in signature_hits:
                h["detection_method"] = "hybrid"
                h["ml_score"] = ml_score
                h["ml_label"] = "malicious"

        return signature_hits

    @staticmethod
    def _ml_candidate(pkt: Packet, score: float) -> dict[str, Any]:
        return {
            "rule_id":          None,
            "rule_name":        "ML anomaly",
            "severity":         "high" if score >= ML_HIGH_THRESHOLD else "medium",
            "category":         "Anomaly",
            "detection_method": "ml",
            "message":          f"ML classifier flagged packet (score={score:.2f})",
            "src_ip":           pkt.src_ip,
            "src_port":         pkt.src_port,
            "dst_ip":           pkt.dst_ip,
            "dst_port":         pkt.dst_port,
            "protocol":         pkt.protocol,
            "ml_score":         score,
            "ml_label":         "malicious",
            "raw_payload":      pkt.payload_text()[:512] or None,
            "extra":            {"flags": pkt.flags, "length": pkt.length},
        }

    # --------------------------------------------------------------------- #
    # Side-effects                                                           #
    # --------------------------------------------------------------------- #
    async def _publish_traffic(self, pkt: Packet) -> None:
        await traffic_bus.publish({
            "type":     "packet",
            "ts":       pkt.ts.isoformat(),
            "protocol": pkt.protocol,
            "src_ip":   pkt.src_ip,
            "dst_ip":   pkt.dst_ip,
            "dst_port": pkt.dst_port,
            "length":   pkt.length,
        })

    async def _maybe_persist_event(self, pkt: Packet) -> None:
        # Sample only 1/N to keep the events table small during demos.
        if self._pkt_count % TRAFFIC_SAMPLE != 0:
            return
        async with AsyncSessionLocal() as db:
            db.add(TrafficEvent(
                protocol=pkt.protocol,
                src_ip=pkt.src_ip, src_port=pkt.src_port,
                dst_ip=pkt.dst_ip, dst_port=pkt.dst_port,
                length=pkt.length, flags=pkt.flags,
            ))
            await db.commit()

    async def _persist_and_broadcast(self, alert_rows: list[dict[str, Any]]) -> None:
        ring_snapshot = list(self._ring)[-SNAPSHOT_TAIL:]
        async with AsyncSessionLocal() as db:
            for row in alert_rows:
                alert = Alert(**row)
                db.add(alert)
                await db.flush()                        # populate alert.id

                pcap_path = write_packet_log(alert.id, ring_snapshot, self.pcap_dir)
                alert.pcap_path = str(pcap_path)
                db.add(PcapRecord(
                    alert_id=alert.id,
                    filename=pcap_path.name,
                    path=str(pcap_path),
                    size_bytes=pcap_path.stat().st_size if pcap_path.exists() else 0,
                    packet_count=len(ring_snapshot),
                ))
                await db.commit()

                self._alert_count += 1
                await alert_bus.publish(self._alert_payload(alert))

    @staticmethod
    def _alert_payload(alert: Alert) -> dict[str, Any]:
        return {
            "type":             "alert",
            "id":               alert.id,
            "ts":               (alert.ts or datetime.now(timezone.utc)).isoformat(),
            "severity":         alert.severity,
            "category":         alert.category,
            "detection_method": alert.detection_method,
            "rule_name":        alert.rule_name,
            "message":          alert.message,
            "src_ip":           alert.src_ip,
            "src_port":         alert.src_port,
            "dst_ip":           alert.dst_ip,
            "dst_port":         alert.dst_port,
            "protocol":         alert.protocol,
            "ml_score":         alert.ml_score,
        }

    # --------------------------------------------------------------------- #
    # Metrics                                                                #
    # --------------------------------------------------------------------- #
    def _tick_pps(self) -> None:
        self._pps_counter += 1
        now = time.monotonic()
        elapsed = now - self._last_pps_ts
        if elapsed >= PPS_WINDOW_SEC:
            self._last_pps_value = self._pps_counter / elapsed
            self._pps_counter = 0
            self._last_pps_ts = now


# Singleton instance — populated from main.py once config is available.
dispatcher: Dispatcher | None = None


def build_dispatcher(pcap_dir, enable_ml: bool = True) -> Dispatcher:
    global dispatcher
    dispatcher = Dispatcher(pcap_dir, enable_ml)
    return dispatcher
