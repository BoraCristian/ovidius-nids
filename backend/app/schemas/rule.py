from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleIn(BaseModel):
    name: str
    description: str | None = None
    category: str = "generic"
    severity: str = "medium"
    enabled: bool = True
    match: dict[str, Any] = Field(default_factory=dict)
    action: str = "alert"


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    enabled: bool | None = None
    match: dict[str, Any] | None = None
    action: str | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    category: str
    severity: str
    enabled: bool
    match: dict[str, Any]
    action: str
    created_at: datetime
    updated_at: datetime
