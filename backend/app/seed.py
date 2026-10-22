"""One-time seed helpers: create admin user and load default rules on boot."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.engine.signatures import CompiledRule, engine
from app.models.rule import Rule
from app.models.user import User


async def seed_admin(db: AsyncSession) -> None:
    settings = get_settings()
    res = await db.execute(select(User).where(User.username == settings.admin_username))
    if res.scalar_one_or_none():
        return
    db.add(User(
        username=settings.admin_username,
        hashed_password=hash_password(settings.admin_password),
        role="admin",
    ))
    await db.commit()


async def seed_rules(db: AsyncSession) -> list[Rule]:
    """Seed (or refresh) the rules table from the YAML file on every boot.

    The previous implementation only inserted brand-new names, which meant
    editing ``default_rules.yaml`` and restarting did *not* change the
    thresholds of rules that were already in the database — confusing for
    anyone tuning the demo. We now also overwrite the ``match``,
    ``severity`` and ``description`` of any existing rule whose name still
    matches an entry in the YAML, while leaving user-created rules alone.
    """
    settings = get_settings()
    path = Path(settings.rules_file)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fp:
        data: list[dict[str, Any]] = yaml.safe_load(fp) or []
    existing = (await db.execute(select(Rule))).scalars().all()
    by_name = {r.name: r for r in existing}

    for entry in data:
        name = entry["name"]
        match = entry.get("match", {})
        category = entry.get("category", "generic")
        severity = entry.get("severity", "medium")
        description = entry.get("description")
        action = entry.get("action", "alert")
        enabled = bool(entry.get("enabled", True))

        if name in by_name:
            # Refresh the seed-managed fields. Leave `enabled` alone so the
            # operator's toggles in the UI survive a restart.
            r = by_name[name]
            r.description = description
            r.category    = category
            r.severity    = severity
            r.match       = match
            r.action      = action
        else:
            db.add(Rule(
                name=name,
                description=description,
                category=category,
                severity=severity,
                enabled=enabled,
                match=match,
                action=action,
            ))
    await db.commit()
    return (await db.execute(select(Rule))).scalars().all()


async def reload_engine_from_db(db: AsyncSession) -> None:
    rows = (await db.execute(select(Rule).where(Rule.enabled == True))).scalars().all()   # noqa: E712
    engine.load([
        CompiledRule(
            id=r.id,
            name=r.name,
            category=r.category,
            severity=r.severity,
            action=r.action,
            match=r.match,
            description=r.description,
        )
        for r in rows
    ])
