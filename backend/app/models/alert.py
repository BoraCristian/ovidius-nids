from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    """A single detection event produced by the engine."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)  # low | medium | high | critical
    category: Mapped[str] = mapped_column(String(64), default="generic")               # e.g. "Recon", "DoS", "Exploit"
    detection_method: Mapped[str] = mapped_column(String(32), default="signature")     # signature | ml | hybrid
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id"), nullable=True, index=True)
    rule_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Connection fields ---
    src_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- ML metadata ---
    ml_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Forensics ---
    pcap_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="new", index=True)  # new | triaged | closed
