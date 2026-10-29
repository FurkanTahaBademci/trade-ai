"""Kisisel backtest: kuyruk, kotalar, sahiplik, worker isi ve paper koprusu."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.api.routers.my_backtests import paper_config_from_backtest
from app.auth.security import hash_token
from app.backtest import service as backtest_service
from app.core import config
from app.core.db import Base, get_db
from app.main import app
from app.models import (
    AppUser,
    BacktestRun,
    BacktestRunPoint,
    BacktestRunTrade,
    CompositeSignalSnapshot,
    IndexDaily,
    Instrument,
    PaperPortfolio,
    PriceDaily,
    UserSession,
)

TABLES = [
    AppUser.__table__,
    UserSession.__table__,
    BacktestRun.__table__,
    BacktestRunPoint.__table__,
    BacktestRunTrade.__table__,
    PaperPortfolio.__table__,
    Instrument.__table__,
    CompositeSignalSnapshot.__table__,
    PriceDaily.__table__,
    IndexDaily.__table__,
]
AYSE = {"Authorization": "Bearer token-1"}
MEHMET = {"Authorization": "Bearer token-2"}
YONETICI = {"Authorization": "Bearer token-3"}
SERVICE = {"X-Admin-Token": "test-service-token"}
PERIOD = {"start_date": "2026-01-01", "end_date": "2026-06-30"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "backtest.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine, tables=TABLES)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    queued: list[int] = []

    async def fake_enqueue(run_id: int) -> bool:
        queued.append(run_id)
        return True

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(backtest_service, "_enqueue", fake_enqueue)
    monkeypatch.setattr(config.get_settings(), "admin_api_token", SERVICE["X-Admin-Token"])
    now = datetime.now(UTC)
    with Session(sync_engine) as session:
        for user_id, email, role in (
            (1, "ayse@example.com", "user"),
            (2, "mehmet@example.com", "user"),
            (3, "yonetici@example.com", "admin"),
        ):
            session.add(
                AppUser(id=user_id, email=email, display_name="", role=role, status="ACTIVE")
            )
            session.flush()
            session.add(
                UserSession(
                    user_id=user_id,
                    token_hash=hash_token(f"token-{user_id}"),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        session.commit()
    with TestClient(app) as client:
        yield {"client": client, "db": sync_engine, "factory": factory, "queued": queued}
    app.dependency_overrides.pop(get_db, None)
    sync_engine.dispose()


def _start(env, headers=AYSE, **body):
    return env["client"].post("/api/me/backtests", headers=headers, json={**PERIOD, **body})


def _set_status(env, run_id, status, **values):
    with Session(env["db"]) as session:
        session.execute(
            update(BacktestRun).where(BacktestRun.id == run_id).values(status=status, **values)
        )
        session.commit()


def test_run_is_queued_with_owner_and_empty_results(env):
    response = _start(env, entry_score=80, exit_score=60)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED" and body["total_return_pct"] is None
    assert body["config"]["entry_score"] == 80 and body["points"] == []
    assert env["queued"] == [body["id"]]
    with Session(env["db"]) as session:
        assert session.get(BacktestRun, body["id"]).owner_id == 1
    assert env["client"].get("/api/me/backtests", headers=AYSE).json()[0]["id"] == body["id"]
    assert env["client"].get("/api/me/backtests", headers=MEHMET).json() == []


def test_one_active_run_and_daily_limit(env, monkeypatch):
    monkeypatch.setattr(config.get_settings(), "backtest_daily_limit_per_user", 2)
    first = _start(env).json()["id"]
    busy = _start(env)
    assert busy.status_code == 409 and busy.json()["detail"]["code"] == "active_run"
    _set_status(env, first, "COMPLETED")
    second = _start(env).json()["id"]
    _set_status(env, second, "FAILED")
    limited = _start(env)
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "daily_limit"
    quota = env["client"].get("/api/me/backtests/quota", headers=AYSE).json()
    assert quota == {
        "daily_limit": 2,
        "used_today": 2,
        "active": 0,
        "max_active": 1,
        "exempt": False,
    }
    # Yonetici hesabi sinirsiz; baska kullanicinin kotasi ayridir.
    assert _start(env, headers=YONETICI).status_code == 202
    assert _start(env, headers=YONETICI).status_code == 202
    assert _start(env, headers=MEHMET).status_code == 202


def test_stale_runs_are_closed_so_users_are_not_stuck(env):
    first = _start(env).json()["id"]
    _set_status(env, first, "RUNNING", created_at=datetime.now(UTC) - timedelta(hours=3))
    assert _start(env).status_code == 202
    with Session(env["db"]) as session:
        stale = session.get(BacktestRun, first)
        assert stale.status == "FAILED" and "zaman aşımı" in stale.error


def test_enqueue_failure_marks_run_failed(env, monkeypatch):
    async def broken(run_id: int) -> bool:
        return False

    monkeypatch.setattr(backtest_service, "_enqueue", broken)
    body = _start(env).json()
    assert body["status"] == "FAILED" and "kuyruğa" in body["error"]


def test_runs_are_private_and_system_api_hides_them(env):
    run_id = _start(env).json()["id"]
    client = env["client"]
    for method, path, payload in [
        ("get", "", None),
        ("get", "/trades", None),
        ("delete", "", None),
        ("post", "/paper", {"name": "Ele geçir"}),
    ]:
        kwargs = {"headers": MEHMET}
        if payload:
            kwargs["json"] = payload
        response = getattr(client, method)(f"/api/me/backtests/{run_id}{path}", **kwargs)
        assert response.status_code == 404, (method, path)
    assert client.get("/api/backtests").json() == []
    assert client.get(f"/api/backtests/{run_id}").status_code == 404
    assert client.get(f"/api/backtests/{run_id}/trades").status_code == 404
    system = client.post("/api/backtests", headers=SERVICE, json=PERIOD)
    assert system.status_code == 202 and system.json()["status"] == "QUEUED"
    assert [row["id"] for row in client.get("/api/backtests").json()] == [system.json()["id"]]


def test_delete_own_run_but_not_while_running(env):
    run_id = _start(env).json()["id"]
    _set_status(env, run_id, "RUNNING")
    assert env["client"].delete(f"/api/me/backtests/{run_id}", headers=AYSE).status_code == 409
    _set_status(env, run_id, "COMPLETED")
    assert env["client"].delete(f"/api/me/backtests/{run_id}", headers=AYSE).status_code == 204
    assert env["client"].get(f"/api/me/backtests/{run_id}", headers=AYSE).status_code == 404


def test_completed_threshold_run_starts_strategy_portfolio(env):
    client = env["client"]
    run_id = _start(env, entry_score=80, exit_score=58, max_positions=8, stop_loss_pct=12).json()[
        "id"
    ]
    early = client.post(f"/api/me/backtests/{run_id}/paper", headers=AYSE, json={"name": "B"})
    assert early.json()["detail"]["code"] == "not_completed"
    _set_status(env, run_id, "COMPLETED")
    created = client.post(
        f"/api/me/backtests/{run_id}/paper",
        headers=AYSE,
        json={"name": "Backtest'ten", "initial_cash": 250000},
    )
    assert created.status_code == 201
    portfolio = created.json()
    assert portfolio["kind"] == "STRATEGY" and portfolio["initial_cash"] == 250000
    assert portfolio["config"]["entry_score"] == 80 and portfolio["config"]["exit_score"] == 58
    assert portfolio["config"]["max_positions"] == 8 and portfolio["config"]["stop_loss_pct"] == 12
    assert portfolio["config"]["max_position_weight_pct"] == 10
    basket = _start(env, headers=MEHMET, strategy="basket").json()["id"]
    _set_status(env, basket, "COMPLETED")
    refused = client.post(f"/api/me/backtests/{basket}/paper", headers=MEHMET, json={"name": "S"})
    assert refused.json()["detail"]["code"] == "unsupported"


def test_paper_config_mapping_rules():
    config = paper_config_from_backtest(
        {
            "entry_score": 75,
            "exit_score": 55,
            "max_positions": 10,
            "max_position_weight": 0.1,
            "max_new_entries_per_day": 0,
            "stop_loss_pct": 15,
            "strategy": "threshold",
        }
    )
    assert config.max_new_entries_per_day == 10  # 0 = sinirsiz -> pozisyon sayisi kadar
    assert config.rebalance_enabled is False and config.max_sector_weight_pct == 0
    with pytest.raises(ValueError, match="Ağırlık"):
        paper_config_from_backtest({"component_weights": {"llm": 1.0}})
    with pytest.raises(ValueError, match="sınırlarının"):
        paper_config_from_backtest({"max_positions": 60, "max_position_weight": 0.01})


async def test_worker_completes_and_fails_runs(env, monkeypatch):
    run_id = _start(env).json()["id"]
    async with env["factory"]() as session:
        result = await backtest_service.execute_backtest_run(session, run_id)
    assert result["status"] == "INSUFFICIENT_DATA"
    with Session(env["db"]) as session:
        run = session.get(BacktestRun, run_id)
        assert run.started_at and run.finished_at and run.signal_count == 0
        assert run.config["execution_price"] == "NEXT_AVAILABLE_CLOSE"
    async with env["factory"]() as session:
        again = await backtest_service.execute_backtest_run(session, run_id)
    assert again["status"] == "INSUFFICIENT_DATA"  # bitmis kosu yeniden hesaplanmaz

    async def explode(session, run, request):
        raise RuntimeError("veri okunamadı")

    monkeypatch.setattr(backtest_service, "_compute", explode)
    _set_status(env, run_id, "COMPLETED")
    failing = _start(env).json()["id"]
    async with env["factory"]() as session:
        failed = await backtest_service.execute_backtest_run(session, failing)
    assert failed["status"] == "FAILED"
    with Session(env["db"]) as session:
        run = session.scalar(select(BacktestRun).where(BacktestRun.id == failing))
        assert "veri okunamadı" in run.error and run.finished_at is not None


def test_stored_request_round_trips_config():
    run = BacktestRun(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
        initial_cash=500000,
        config={"entry_score": 82, "exit_score": 60, "strategy": "threshold"},
    )
    request = backtest_service.stored_request(run)
    assert request.entry_score == 82 and request.initial_cash == 500000
    assert request.start_date == date(2026, 1, 1)
