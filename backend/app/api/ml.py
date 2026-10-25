"""Machine-learning model management endpoints."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.engine.ml_detector import detector
from app.models.ml_model import MLModel
from app.schemas.ml import MLModelOut, MLTrainRequest

log = logging.getLogger("nids.ml")

router = APIRouter(prefix="/api/ml", tags=["ml"], dependencies=[Depends(get_current_user)])

# The model name becomes part of the artifact's filename, so it must not be
# able to contain path separators or "..".
_MODEL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


async def _unique_name(db: AsyncSession, base: str) -> str:
    """
    Return `base` if it's free, otherwise `base-2`, `base-3`, ... until we
    find an unused `MLModel.name`.  Prevents the UNIQUE-constraint 500 that
    users used to hit when clicking "Train + activate" twice in a row.
    """
    existing = {
        n for (n,) in (await db.execute(select(MLModel.name))).all()
    }
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"


@router.get("/models", response_model=list[MLModelOut])
async def list_models(db: AsyncSession = Depends(get_db)) -> list[MLModelOut]:
    rows = (await db.execute(select(MLModel).order_by(MLModel.id.desc()))).scalars().all()
    return [MLModelOut.model_validate(r) for r in rows]


@router.post("/train", response_model=MLModelOut)
async def train(req: MLTrainRequest, db: AsyncSession = Depends(get_db)) -> MLModelOut:
    settings = get_settings()
    if not _MODEL_NAME_RE.fullmatch(req.name) or ".." in req.name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Model name must be 1-64 letters, digits, '.', '_' or '-', starting with a letter or digit.",
        )

    try:
        result = detector.train_synthetic(algorithm=req.algorithm)
    except Exception as exc:  # training itself blew up (sklearn / numpy)
        log.exception("ML training failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Training failed: {exc}",
        )

    ts = int(datetime.now(timezone.utc).timestamp())
    # Pick a free name first, so the artifact filename matches the DB row.
    name = await _unique_name(db, req.name)
    path = Path(settings.ml_model_dir) / f"{name}-{ts}.joblib"
    detector.save(path)

    if req.activate:
        # Deactivate old models, flag this one
        for m in (await db.execute(select(MLModel))).scalars().all():
            m.is_active = False
        await db.commit()

    m = MLModel(
        name=name,
        algorithm=result["algorithm"],
        path=str(path),
        trained_on=req.dataset,
        accuracy=result["metrics"]["accuracy"],
        precision=result["metrics"]["precision"],
        recall=result["metrics"]["recall"],
        f1=result["metrics"]["f1"],
        feature_importance=result.get("feature_importance"),
        notes=f"Trained on {req.dataset} ({result['algorithm']})",
        is_active=bool(req.activate),
    )
    db.add(m)
    try:
        await db.commit()
    except Exception as exc:  # last-resort safety net for unexpected DB errors
        await db.rollback()
        log.exception("Failed to persist trained ML model")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not save model: {exc}",
        )
    await db.refresh(m)
    return MLModelOut.model_validate(m)


@router.post("/activate/{model_id}", response_model=MLModelOut)
async def activate(model_id: int, db: AsyncSession = Depends(get_db)) -> MLModelOut:
    m = (await db.execute(select(MLModel).where(MLModel.id == model_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if not Path(m.path).exists():
        raise HTTPException(status.HTTP_410_GONE, "Model file missing on disk")
    detector.load(m.path)
    for other in (await db.execute(select(MLModel))).scalars().all():
        other.is_active = False
    m.is_active = True
    await db.commit()
    await db.refresh(m)
    return MLModelOut.model_validate(m)


@router.get("/status")
async def status_() -> dict:
    return {"active": detector.is_active(), "feature_names": detector.feature_names}
