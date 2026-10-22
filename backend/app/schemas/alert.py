from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


Severity = Literal["low", "medium", "high", "critical"]
DetectionMethod = Literal["signature", "ml", "hybrid"]
AlertStatus = Literal["new", "triaged", "closed"]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    severity: Severity
    category: str
    detection_method: DetectionMethod
    rule_id: int | None = None
    rule_name: str | None = None
    message: str
    src_ip: str | None = None
    src_port: int | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    protocol: str | None = None
    ml_score: float | None = None
    ml_label: str | None = None
    pcap_path: str | None = None
    raw_payload: str | None = None
    extra: dict[str, Any] | None = None
    status: AlertStatus


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    severity: Severity | None = None


class AlertStats(BaseModel):
    total: int
    new: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_method: dict[str, int]
