from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TimeBucket(BaseModel):
    ts: datetime
    count: int


class TopItem(BaseModel):
    key: str
    count: int


class DashboardSummary(BaseModel):
    alerts_total: int
    alerts_open: int
    packets_seen: int
    pps: float
    top_src_ips: list[TopItem]
    top_dst_ports: list[TopItem]
    alerts_timeline: list[TimeBucket]
    severity_distribution: dict[str, int]
    method_distribution: dict[str, int]
