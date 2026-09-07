"""Dinamik collector takvimi regresyon testleri."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routers import schedules as schedule_router
from app.main import app
from app.scheduling import service
from app.schemas.schedule import ScheduleUpdate


def test_default_schedule_definitions_are_unique_and_safe():
    names = [item.name for item in service.SCHEDULE_DEFINITIONS]
    jobs = [item.job_name for item in service.SCHEDULE_DEFINITIONS]

    assert len(names) == len(set(names))
    assert len(jobs) == len(set(jobs))
    assert service.DEFINITION_BY_NAME["news"].default_interval_minutes == 5
    assert all(
        item.default_interval_minutes >= item.minimum_interval_minutes
        for item in service.SCHEDULE_DEFINITIONS
    )


def test_initial_daily_run_uses_istanbul_wall_clock(monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(tz="Europe/Istanbul"))
    definition = service.DEFINITION_BY_NAME["instruments"]

    before = service.next_initial_run(definition, datetime(2026, 9, 7, 2, 0, tzinfo=UTC))
    after = service.next_initial_run(definition, datetime(2026, 9, 7, 5, 0, tzinfo=UTC))

    assert before == datetime(2026, 9, 7, 3, 0, tzinfo=UTC)
    assert after == datetime(2026, 9, 8, 3, 0, tzinfo=UTC)


def test_advance_run_skips_missed_slots_without_drift():
    previous = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
    now = datetime(2026, 9, 7, 9, 17, tzinfo=UTC)

    assert service.advance_run(previous, 5, now) == datetime(2026, 9, 7, 9, 20, tzinfo=UTC)
    assert service.advance_run(now + timedelta(minutes=2), 5, now) == now + timedelta(minutes=2)


async def test_dispatcher_stops_when_another_worker_holds_lock():
    class LockedRedis:
        async def set(self, *args, **kwargs):
            return False

    result = await service.dispatch_due_schedules({"redis": LockedRedis()})
    assert result == {"status": "locked", "enqueued": 0}


def test_schedule_update_requires_a_change():
    with pytest.raises(ValidationError):
        ScheduleUpdate()


def test_admin_token_required_in_production(monkeypatch):
    monkeypatch.setattr(
        schedule_router,
        "get_settings",
        lambda: SimpleNamespace(environment="production", admin_api_token=""),
    )
    with pytest.raises(HTTPException) as exc:
        schedule_router.require_admin_token()
    assert exc.value.status_code == 503


def test_admin_token_rejects_invalid_value(monkeypatch):
    monkeypatch.setattr(
        schedule_router,
        "get_settings",
        lambda: SimpleNamespace(environment="production", admin_api_token="secret"),
    )
    with pytest.raises(HTTPException) as exc:
        schedule_router.require_admin_token("wrong")
    assert exc.value.status_code == 401
    assert schedule_router.require_admin_token("secret") == "admin-token"


def test_schedule_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "/api/schedules" in paths
    assert "/api/schedules/{name}" in paths
    assert "/api/schedules/{name}/run" in paths
