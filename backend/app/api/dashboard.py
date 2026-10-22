"""Aggregated metrics for the SIEM dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.engine import dispatcher as _disp
from app.models.alert import Alert
from app.schemas.dashboard import DashboardSummary, TimeBucket, TopItem

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)

TIMELINE_HOURS = 6
TIMELINE_BUCKETS = 36                          # 36 * 10 min = 6 h
BUCKET_WIDTH_SEC = (TIMELINE_HOURS * 3600) // TIMELINE_BUCKETS   # 600 s


@router.get("/summary", response_model=DashboardSummary)
async def summary(db: AsyncSession = Depends(get_db)) -> DashboardSummary:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    timeline_start = now - timedelta(hours=TIMELINE_HOURS)

    # --- 24h totals ---
    total_alerts = await _count(db, Alert.ts >= window_start)
    open_alerts  = await _count(db, Alert.ts >= window_start, Alert.status == "new")

    # --- top source IPs / destination ports ---
    top_src = await _top_items(db, Alert.src_ip,   window_start, limit=8, not_null=True)
    top_dst = await _top_items(db, Alert.dst_port, window_start, limit=8, not_null=True)

    # --- severity + method breakdown ---
    severity_dist = dict(await _group_counts(db, Alert.severity,         window_start))
    method_dist   = dict(await _group_counts(db, Alert.detection_method, window_start))

    # --- 10-minute-bucketed timeline over last 6h (single query) ---
    timeline = await _alerts_timeline(db, timeline_start)

    # --- live engine metrics ---
    packets_seen = _disp.dispatcher.packets if _disp.dispatcher else 0
    pps          = round(_disp.dispatcher.pps(), 2) if _disp.dispatcher else 0.0

    return DashboardSummary(
        alerts_total=total_alerts,
        alerts_open=open_alerts,
        packets_seen=packets_seen,
        pps=pps,
        top_src_ips=top_src,
        top_dst_ports=top_dst,
        alerts_timeline=timeline,
        severity_distribution=severity_dist,
        method_distribution=method_dist,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
async def _count(db: AsyncSession, *where) -> int:
    row = await db.execute(select(func.count()).select_from(Alert).where(*where))
    return int(row.scalar_one() or 0)


async def _top_items(
    db: AsyncSession,
    column,
    since: datetime,
    *,
    limit: int,
    not_null: bool = False,
) -> list[TopItem]:
    stmt = (
        select(column, func.count())
        .where(Alert.ts >= since)
        .group_by(column)
        .order_by(func.count().desc())
        .limit(limit)
    )
    if not_null:
        stmt = stmt.where(column.is_not(None))
    rows = (await db.execute(stmt)).all()
    return [TopItem(key=str(k or "-"), count=int(c)) for k, c in rows]


async def _group_counts(db: AsyncSession, column, since: datetime) -> list[tuple[str, int]]:
    rows = (await db.execute(
        select(column, func.count()).where(Alert.ts >= since).group_by(column)
    )).all()
    return [(str(k), int(v)) for k, v in rows]


async def _alerts_timeline(db: AsyncSession, start: datetime) -> list[TimeBucket]:
    """Return `TIMELINE_BUCKETS` zero-filled 10-minute buckets over the last 6h.

    Implemented as a single SELECT that pulls only timestamps, then buckets in
    Python.  Replaces the old loop that fired 36 round-trips per refresh.
    """
    rows = (await db.execute(
        select(Alert.ts).where(Alert.ts >= start)
    )).scalars().all()

    counts = [0] * TIMELINE_BUCKETS
    start_ts = start.timestamp()
    for ts in rows:
        # `Alert.ts` is timezone-aware UTC
        idx = int((ts.timestamp() - start_ts) // BUCKET_WIDTH_SEC)
        if 0 <= idx < TIMELINE_BUCKETS:
            counts[idx] += 1

    return [
        TimeBucket(ts=start + timedelta(seconds=i * BUCKET_WIDTH_SEC), count=c)
        for i, c in enumerate(counts)
    ]
