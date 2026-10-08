"""Readiness must fail on unavailable dependencies without leaking errors."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.routers import health
from app.main import app


@pytest.mark.parametrize("failed", [None, "db", "redis", "timeout"])
def test_readiness_dependency_failures(monkeypatch, failed):
    monkeypatch.setattr(
        health,
        "ping_db",
        AsyncMock(
            side_effect=RuntimeError("private connection details") if failed == "db" else None
        ),
    )
    monkeypatch.setattr(
        health,
        "ping_redis",
        AsyncMock(
            side_effect=TimeoutError()
            if failed == "timeout"
            else RuntimeError("private connection details")
            if failed == "redis"
            else None
        ),
    )
    response = TestClient(app).get("/health/ready")
    assert response.status_code == (503 if failed else 200)
    assert response.json()["status"] == ("degraded" if failed else "ok")
    assert "private" not in response.text


def test_monitoring_failure_does_not_misreport_redis_outage(monkeypatch):
    monkeypatch.setattr(health, "ping_db", AsyncMock())
    monkeypatch.setattr(health, "ping_redis", AsyncMock())
    monkeypatch.setattr(
        health, "get_monitoring_report", AsyncMock(side_effect=ValueError("bad data"))
    )
    response = TestClient(app).get("/health/detailed")
    assert response.json() == {
        "db": "ok",
        "redis": "ok",
        "monitoring": None,
        "status": "degraded",
    }


def test_readiness_does_not_wait_for_collectors(monkeypatch):
    monkeypatch.setattr(health, "ping_db", AsyncMock())
    monkeypatch.setattr(health, "ping_redis", AsyncMock())
    monitoring = AsyncMock(side_effect=AssertionError("must not read collector state"))
    monkeypatch.setattr(health, "get_monitoring_report", monitoring)
    assert TestClient(app).get("/health/ready").status_code == 200
    monitoring.assert_not_called()
