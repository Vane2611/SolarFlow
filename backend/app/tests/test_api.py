"""Stub API tests — full test suite implemented in FEAT-005."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_manual_override_invalid_action_returns_422() -> None:
    response = client.post(
        "/api/control/manual-override",
        json={"action": "arbitrary_command", "duration_seconds": 60},
    )
    assert response.status_code == 422


def test_manual_override_fan_on_returns_200() -> None:
    response = client.post(
        "/api/control/manual-override",
        json={"action": "fan_on", "duration_seconds": 60},
    )
    assert response.status_code == 200


def test_readings_history_returns_list() -> None:
    response = client.get("/api/readings/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_alerts_returns_list() -> None:
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_control_mode_get() -> None:
    response = client.get("/api/control/mode")
    assert response.status_code == 200


def test_control_mode_set() -> None:
    response = client.post("/api/control/mode", json={"mode": "predictive"})
    assert response.status_code == 200
    assert response.json()["mode"] == "predictive"


def test_devices_status() -> None:
    response = client.get("/api/devices/status")
    assert response.status_code == 200


def test_analytics_comparison() -> None:
    response = client.get("/api/analytics/comparison")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
