from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MLModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    algorithm: str
    path: str
    trained_on: str | None = None
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    feature_importance: dict | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime


class MLTrainRequest(BaseModel):
    name: str = "baseline-rf"
    algorithm: str = "random_forest"
    dataset: str = "synthetic"
    activate: bool = True
