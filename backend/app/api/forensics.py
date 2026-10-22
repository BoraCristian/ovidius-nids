"""Forensics: list captured PCAPs, fetch packet log for an alert."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import Alert
from app.models.pcap import PcapRecord
from app.schemas.pcap import PcapOut

router = APIRouter(prefix="/api/forensics", tags=["forensics"], dependencies=[Depends(get_current_user)])


@router.get("/pcaps", response_model=list[PcapOut])
async def list_pcaps(db: AsyncSession = Depends(get_db)) -> list[PcapOut]:
    rows = (await db.execute(select(PcapRecord).order_by(PcapRecord.id.desc()).limit(200))).scalars().all()
    return [PcapOut.model_validate(r) for r in rows]


@router.get("/alert/{alert_id}/packets")
async def packets_for_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    if not alert.pcap_path:
        return []
    p = Path(alert.pcap_path)
    if not p.exists():
        return []
    out: list[dict] = []
    with p.open("r", encoding="utf-8") as fp:
        for line in fp:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


@router.get("/alert/{alert_id}/download")
async def download_pcap_jsonl(alert_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert or not alert.pcap_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No capture available")
    p = Path(alert.pcap_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capture file missing")
    return FileResponse(path=str(p), filename=p.name, media_type="application/jsonl")
