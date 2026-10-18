"""Worker kaynak ayarlari: es zamanli is siniri ve slotlardan bagimsiz heartbeat."""

import asyncio

import pytest

from app.core.config import Settings
from app.tasks import schedule


def test_max_jobs_defaults_low_and_is_configurable(monkeypatch):
    assert Settings().worker_max_jobs == 3
    monkeypatch.setenv("WORKER_MAX_JOBS", "5")
    assert Settings().worker_max_jobs == 5
    assert schedule.WorkerSettings.max_jobs >= 1


def test_max_jobs_rejects_zero(monkeypatch):
    monkeypatch.setenv("WORKER_MAX_JOBS", "0")
    with pytest.raises(ValueError):
        Settings()


def test_heartbeat_loop_runs_outside_job_slots(monkeypatch):
    writes: list[int] = []

    async def fake_write() -> None:
        writes.append(1)

    monkeypatch.setattr(schedule, "_write_heartbeat", fake_write)
    monkeypatch.setattr(schedule, "HEARTBEAT_INTERVAL_SECONDS", 0.01)

    async def run() -> None:
        ctx: dict = {}
        await schedule.startup(ctx)
        await asyncio.sleep(0.05)
        await schedule.shutdown(ctx)
        assert ctx["heartbeat_task"].cancelled()

    asyncio.run(run())
    # startup bir kez + dongu en az bir kez yazar
    assert len(writes) >= 2
