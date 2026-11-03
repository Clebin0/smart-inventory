import os
import uuid

os.environ["APP_TOKEN"] = "test-token"
os.environ["DATABASE_URL"] = "sqlite:///./smart_inventory_test.db"

from fastapi.testclient import TestClient

import app as app_module
from app import app

client = TestClient(app)
AUTH = {"X-App-Token": "test-token"}


def create_asset():
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/assets",
        headers=AUTH,
        json={
            "tag": f"TEST-{suffix}",
            "name": "Notebook de teste",
            "category": "Notebook",
            "serial_number": f"SN-{suffix}",
            "location": "Laboratorio",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_requires_token():
    response = client.get("/assets")
    assert response.status_code == 401


def test_missing_server_token_fails_closed(monkeypatch):
    monkeypatch.setattr(app_module, "APP_TOKEN", "")
    response = client.get("/assets", headers=AUTH)
    assert response.status_code == 503


def test_in_use_asset_requires_assignee():
    response = client.post(
        "/assets",
        headers=AUTH,
        json={
            "tag": f"TEST-{uuid.uuid4().hex[:10]}",
            "name": "Notebook sem responsável",
            "category": "Notebook",
            "status": "in_use",
        },
    )
    assert response.status_code == 422


def test_asset_lifecycle_is_audited():
    asset = create_asset()
    asset_id = asset["id"]

    invalid_check_in = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={"action": "check_in", "actor": "Operador"},
    )
    assert invalid_check_in.status_code == 409

    checkout = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={
            "action": "check_out",
            "actor": "Operador",
            "assigned_to": "Pessoa de teste",
        },
    )
    assert checkout.status_code == 201

    duplicate_checkout = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={
            "action": "check_out",
            "actor": "Operador",
            "assigned_to": "Outra pessoa",
        },
    )
    assert duplicate_checkout.status_code == 409

    checkin = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={"action": "check_in", "actor": "Operador"},
    )
    assert checkin.status_code == 201

    current = client.get(f"/assets/{asset_id}", headers=AUTH).json()
    assert current["status"] == "available"
    assert current["assigned_to"] is None

    history = client.get(f"/assets/{asset_id}/movements", headers=AUTH)
    assert history.status_code == 200
    assert [item["action"] for item in history.json()] == ["check_in", "check_out"]


def test_transfer_requires_destination():
    asset = create_asset()
    response = client.post(
        f"/assets/{asset['id']}/movements",
        headers=AUTH,
        json={"action": "transfer", "actor": "Operador"},
    )
    assert response.status_code == 422


def test_maintenance_clears_previous_assignee():
    asset = create_asset()
    asset_id = asset["id"]
    checkout = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={
            "action": "check_out",
            "actor": "Operador",
            "assigned_to": "Pessoa de teste",
        },
    )
    assert checkout.status_code == 201

    maintenance = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={"action": "maintenance", "actor": "Técnico"},
    )
    assert maintenance.status_code == 201

    current = client.get(f"/assets/{asset_id}", headers=AUTH).json()
    assert current["status"] == "maintenance"
    assert current["assigned_to"] is None


def test_update_cannot_bypass_movement_history():
    asset = create_asset()
    asset_id = asset["id"]
    checkout = client.post(
        f"/assets/{asset_id}/movements",
        headers=AUTH,
        json={
            "action": "check_out",
            "actor": "Operador",
            "assigned_to": "Pessoa de teste",
        },
    )
    assert checkout.status_code == 201

    response = client.put(
        f"/assets/{asset_id}",
        headers=AUTH,
        json={
            "tag": asset["tag"],
            "name": asset["name"],
            "category": asset["category"],
            "serial_number": asset["serial_number"],
            "location": asset["location"],
            "status": "available",
            "assigned_to": None,
            "notes": asset["notes"],
        },
    )
    assert response.status_code == 409


def test_history_returns_not_found_for_unknown_asset():
    response = client.get("/assets/99999999/movements", headers=AUTH)
    assert response.status_code == 404
