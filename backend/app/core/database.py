"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Shared declarative base for ORM models."""


class UTCDateTime(TypeDecorator):
    """A timestamp column that always comes back timezone-aware, in UTC.

    SQLite has no timezone type, so a plain ``DateTime(timezone=True)`` reads
    back naive values. Serialised without an offset, browsers would then show
    UTC times as if they were local time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a scoped async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables (dev convenience; use Alembic for production)."""
    # Import models so SQLAlchemy registers them before create_all
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
