"""Storage vacuum endpoint and script tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routers.system import router as system_router
from app.core.config import Settings


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(system_router)
    return app


def test_vacuum_endpoint_requires_admin_token_in_production(test_app, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.schedules.get_settings",
        lambda: Settings(environment="production", admin_api_token="test-secret"),
    )
    client = TestClient(test_app)

    # Missing token
    resp = client.post("/api/system/storage/vacuum")
    assert resp.status_code == 401

    # Wrong token
    resp = client.post(
        "/api/system/storage/vacuum", headers={"X-Admin-Token": "wrong"}
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_vacuum_endpoint_executes_with_valid_token(test_app, monkeypatch):
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr("app.api.routers.system.engine", sqlite_engine)
    monkeypatch.setattr(
        "app.api.routers.schedules.get_settings",
        lambda: Settings(environment="production", admin_api_token="test-secret"),
    )

    client = TestClient(test_app)
    resp = client.post(
        "/api/system/storage/vacuum", headers={"X-Admin-Token": "test-secret"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    await sqlite_engine.dispose()


@pytest.mark.anyio
async def test_vacuum_storage_script_runs(monkeypatch):
    import sys
    from pathlib import Path

    sqlite_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import vacuum_storage

    monkeypatch.setattr(vacuum_storage, "engine", sqlite_engine)

    result = await vacuum_storage.vacuum_storage()
    assert result["ok"] is True
    await sqlite_engine.dispose()
