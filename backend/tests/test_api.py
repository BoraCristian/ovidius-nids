"""End-to-end API tests against the full app (in-process, throwaway database)."""
from __future__ import annotations

import json
import time

import jwt
import pytest
from starlette.websockets import WebSocketDisconnect

from helpers import is_documentation_ip

ATTACK_KINDS = ["nmap", "ssh_brute", "icmp_flood", "sqli", "cmd_inject", "reverse_shell"]


def fire(client, headers, kind):
    r = client.post("/api/sim/attack", json={"kind": kind}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# Health and authentication                                                    #
# --------------------------------------------------------------------------- #
def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["debug"] is True          # drives the login page's demo hint


def test_login_with_demo_account(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_login_rejects_wrong_password(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_protected_routes_require_a_token(client, auth_headers):
    assert client.get("/api/alerts").status_code == 401
    assert client.get("/api/alerts", headers=auth_headers).status_code == 200


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_token_signed_with_old_default_secret_is_rejected(client):
    forged = jwt.encode({"sub": "admin", "exp": int(time.time()) + 600},
                        "dev-secret-change-me", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_generated_secret_key_is_persisted(client):
    from app.core.config import get_settings

    settings = get_settings()
    stored = (settings.data_dir / ".secret_key").read_text(encoding="utf-8").strip()
    assert stored == settings.secret_key and len(stored) >= 40


# --------------------------------------------------------------------------- #
# Attack Console -> detection -> forensics                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind", ATTACK_KINDS)
def test_every_attack_in_the_console_produces_alerts(client, auth_headers, kind):
    result = fire(client, auth_headers, kind)
    assert result["alerts_generated"] >= 1
    assert result["target"] == "10.0.0.10"
    assert is_documentation_ip(result["attacker"])


def test_unknown_attack_kind_is_rejected(client, auth_headers):
    r = client.post("/api/sim/attack", json={"kind": "teleport"}, headers=auth_headers)
    assert r.status_code == 400


def test_alert_has_downloadable_forensic_capture(client, auth_headers):
    fire(client, auth_headers, "sqli")
    alert = client.get("/api/alerts?limit=1", headers=auth_headers).json()[0]
    assert alert["rule_name"] == "HTTP SQL injection pattern"

    r = client.get(f"/api/forensics/alert/{alert['id']}/download", headers=auth_headers)
    assert r.status_code == 200
    packets = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert "'1'='1" in packets[-1]["payload_preview"]       # the triggering packet


def test_dashboard_summary_counts_alerts(client, auth_headers):
    fire(client, auth_headers, "icmp_flood")
    summary = client.get("/api/dashboard/summary", headers=auth_headers).json()
    assert summary["alerts_total"] > 0
    assert summary["packets_seen"] > 0


# --------------------------------------------------------------------------- #
# Rules and ML                                                                 #
# --------------------------------------------------------------------------- #
def test_rules_can_be_created_and_deleted(client, auth_headers):
    rule = {"name": "Test: FTP control channel", "category": "Policy", "severity": "low",
            "match": {"protocol": "tcp", "dst_port": 21}}
    created = client.post("/api/rules", json=rule, headers=auth_headers)
    assert created.status_code == 201
    assert client.post("/api/rules", json=rule, headers=auth_headers).status_code == 409

    rule_id = created.json()["id"]
    assert client.delete(f"/api/rules/{rule_id}", headers=auth_headers).status_code == 204
    names = [r["name"] for r in client.get("/api/rules", headers=auth_headers).json()]
    assert rule["name"] not in names


def test_trained_model_upgrades_signature_alerts_to_hybrid(client, auth_headers):
    r = client.post("/api/ml/train", json={"name": "ci-rf", "algorithm": "random_forest"},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    model = r.json()
    assert model["is_active"] and model["accuracy"] >= 0.95

    fire(client, auth_headers, "nmap")
    recent = client.get("/api/alerts?limit=50", headers=auth_headers).json()
    assert any(a["detection_method"] == "hybrid" for a in recent)


@pytest.mark.parametrize("name", ["../escape", r"..\escape", "a/b", "", ".hidden", "x" * 65])
def test_train_rejects_unsafe_model_names(client, auth_headers, name):
    r = client.post("/api/ml/train", json={"name": name}, headers=auth_headers)
    assert r.status_code == 400, r.text


# --------------------------------------------------------------------------- #
# WebSockets                                                                   #
# --------------------------------------------------------------------------- #
def test_websocket_without_token_is_closed(client):
    with client.websocket_connect("/ws/alerts") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 4401


def test_websocket_streams_new_alerts(client, auth_headers):
    token = auth_headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        time.sleep(0.3)                      # let the handler subscribe to the alert bus
        fire(client, auth_headers, "reverse_shell")
        msg = ws.receive_json()
    assert msg["type"] == "alert"
    assert msg["rule_name"] == "Reverse shell handshake (/bin/sh)"
