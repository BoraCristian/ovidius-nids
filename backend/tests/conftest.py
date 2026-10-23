"""Shared test setup.

The app reads its settings once, at import time, so every path is pointed at a
throwaway directory *before* anything under `app` is imported. Tests never touch
the real backend/nids.db, data/models or data/pcaps.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
_TMP = Path(tempfile.mkdtemp(prefix="nids-tests-"))
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)

os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
    "DATA_DIR": str(_TMP),
    "PCAP_DIR": str(_TMP / "pcaps"),
    "ML_MODEL_DIR": str(_TMP / "models"),
    "RULES_FILE": str(BACKEND_DIR / "data" / "rules" / "default_rules.yaml"),
    "SECRET_KEY": "",
    "DEBUG": "true",
    "SIMULATE_TRAFFIC": "true",
    "SIM_ATTACKS_ON_DEMAND_ONLY": "true",
    "SIM_BENIGN_TRAFFIC": "false",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "admin",
})
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def client():
    """The full FastAPI app (lifespan included: DB, seeding, simulator)."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
