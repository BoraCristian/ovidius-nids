"""CRUD for signature rules with live engine reload."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.rule import Rule
from app.schemas.rule import RuleIn, RuleOut, RuleUpdate
from app.seed import reload_engine_from_db

router = APIRouter(prefix="/api/rules", tags=["rules"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)) -> list[RuleOut]:
    rows = (await db.execute(select(Rule).order_by(Rule.id))).scalars().all()
    return [RuleOut.model_validate(r) for r in rows]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: RuleIn, db: AsyncSession = Depends(get_db)) -> RuleOut:
    exists = (await db.execute(select(Rule).where(Rule.name == payload.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "A rule with this name already exists")
    rule = Rule(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await reload_engine_from_db(db)
    return RuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, payload: RuleUpdate, db: AsyncSession = Depends(get_db)) -> RuleOut:
    rule = (await db.execute(select(Rule).where(Rule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    await db.commit()
    await db.refresh(rule)
    await reload_engine_from_db(db)
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> None:
    rule = (await db.execute(select(Rule).where(Rule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    await db.delete(rule)
    await db.commit()
    await reload_engine_from_db(db)
