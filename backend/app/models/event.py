from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime


class TrafficEvent(Base):
    """A processed flow/packet summary. Kept small and rolled over; used for stats & timelines."""

    __tablename__ = "traffic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc), index=True
    )
    protocol: Mapped[str] = mapped_column(String(16))
    src_ip: Mapped[str] = mapped_column(String(64), index=True)
    src_port: Mapped[int] = mapped_column(Integer, default=0)
    dst_ip: Mapped[str] = mapped_column(String(64), index=True)
    dst_port: Mapped[int] = mapped_column(Integer, default=0)
    length: Mapped[int] = mapped_column(Integer, default=0)
    flags: Mapped[str | None] = mapped_column(String(16), nullable=True)
