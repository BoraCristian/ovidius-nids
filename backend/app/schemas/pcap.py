from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PcapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int | None = None
    filename: str
    path: str
    size_bytes: int
    packet_count: int
    created_at: datetime
