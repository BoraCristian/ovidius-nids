"""Alerts: list / filter / update status / stats."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut, AlertStats, AlertUpdate

router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    severity: str | None = Query(None),
    status_f: str | None = Query(None, alias="status"),
    method: str | None = Query(None),
    src_ip: str | None = Query(None),
    q: str | None = Query(None, description="free-text search across message + rule_name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AlertOut]:
    stmt = select(Alert).order_by(Alert.ts.desc())
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if status_f:
        stmt = stmt.where(Alert.status == status_f)
    if method:
        stmt = stmt.where(Alert.detection_method == method)
    if src_ip:
        stmt = stmt.where(Alert.src_ip == src_ip)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Alert.message).like(like))
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]


@router.get("/stats", response_model=AlertStats)
async def alert_stats(db: AsyncSession = Depends(get_db), hours: int = 24) -> AlertStats:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    total = (await db.execute(select(func.count()).select_from(Alert).where(Alert.ts >= since))).scalar_one()
    open_ = (await db.execute(select(func.count()).select_from(Alert).where(Alert.ts >= since, Alert.status == "new"))).scalar_one()

    async def bucket(column) -> dict[str, int]:
        rows = await db.execute(
            select(column, func.count()).where(Alert.ts >= since).group_by(column)
        )
        return {str(k): int(v) for k, v in rows.all()}

    return AlertStats(
        total=int(total or 0),
        new=int(open_ or 0),
        by_severity=await bucket(Alert.severity),
        by_category=await bucket(Alert.category),
        by_method=await bucket(Alert.detection_method),
    )


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> AlertOut:
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return AlertOut.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(alert_id: int, payload: AlertUpdate, db: AsyncSession = Depends(get_db)) -> AlertOut:
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    data: dict[str, Any] = payload.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(alert, k, v)
    await db.commit()
    await db.refresh(alert)
    return AlertOut.model_validate(alert)
