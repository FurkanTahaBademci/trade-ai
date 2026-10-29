"""Kullanici portfoyleri API'si: olusturma, sinirlar, sahiplik (IDOR) ve manuel emirler."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.auth.security import hash_token
from app.core import config
from app.core.db import Base, get_db
from app.main import app
from app.models import (
    AppUser,
    Instrument,
    PaperOrder,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
    UserSession,
)
from app.paper.risk import RiskConfig

TABLES = [
    AppUser.__table__,
    UserSession.__table__,
    Instrument.__table__,
    PaperPortfolio.__table__,
    PaperPosition.__table__,
    PaperTrade.__table__,
    PaperPortfolioSnapshot.__table__,
    PaperOrder.__table__,
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "paper.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine, tables=TABLES)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    async def model_risk():
        return RiskConfig(stop_loss_pct=Decimal(15))

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.api.routers.my_portfolios.load_risk_config", model_risk)
    monkeypatch.setattr("app.api.routers.paper.load_risk_config", model_risk)
    now = datetime.now(UTC)
    with Session(sync_engine) as session:
        for user_id, email in ((1, "ayse@example.com"), (2, "mehmet@example.com")):
            session.add(
                AppUser(id=user_id, email=email, display_name="", role="user", status="ACTIVE")
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
        session.add_all(
            [
                Instrument(ticker="THYAO", name="Türk Hava Yolları", kap_member_oid="1"),
                Instrument(ticker="ASELS", name="Aselsan", kap_member_oid="2"),
                Instrument(ticker="ESKI", name="Eski", kap_member_oid="3", is_active=False),
            ]
        )
        session.add(
            PaperPortfolio(
                name="Ana Paper Portföy",
                kind="STRATEGY",
                strategy_version="paper-v5",
                base_currency="TRY",
                status="ACTIVE",
                initial_cash=1_000_000,
                cash_balance=1_000_000,
                realized_pnl=0,
                total_fees=0,
            )
        )
        session.commit()
    with TestClient(app) as client:
        yield {"client": client, "db": sync_engine}
    app.dependency_overrides.pop(get_db, None)
    sync_engine.dispose()


AYSE = {"Authorization": "Bearer token-1"}
MEHMET = {"Authorization": "Bearer token-2"}


def _create(env, headers=AYSE, **body):
    payload = {"name": "Deneme", "kind": "MANUAL", "initial_cash": 100_000, **body}
    return env["client"].post("/api/me/portfolios", headers=headers, json=payload)


def test_requires_session(env):
    assert env["client"].get("/api/me/portfolios").status_code == 401
    assert _create(env, headers={}).status_code == 401


def test_create_strategy_from_template_and_manual(env):
    strategy = _create(env, name="Temkinli", kind="STRATEGY", template="temkinli")
    assert strategy.status_code == 201
    body = strategy.json()
    assert body["kind"] == "STRATEGY" and body["config"]["entry_score"] == 80
    assert body["started_on"] and body["cash_balance"] == 100_000
    manual = _create(env, name="Elle")
    assert manual.json()["kind"] == "MANUAL" and manual.json()["config"] is None
    default = _create(env, name="Varsayılan", kind="STRATEGY")
    assert default.json()["config"]["entry_score"] == 75

    listing = env["client"].get("/api/me/portfolios", headers=AYSE).json()
    assert [row["name"] for row in listing] == ["Temkinli", "Elle", "Varsayılan"]
    assert listing[0]["total_equity"] == 100_000 and listing[0]["snapshot_date"] is None
    assert env["client"].get("/api/me/portfolios", headers=MEHMET).json() == []


def test_limits_duplicate_names_and_validation(env, monkeypatch):
    monkeypatch.setattr(config.get_settings(), "paper_max_portfolios_per_user", 2)
    assert _create(env, name="A").status_code == 201
    duplicate = _create(env, name="A")
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "duplicate_name"
    assert _create(env, name="B").status_code == 201
    assert _create(env, name="C").json()["detail"]["code"] == "portfolio_limit"
    # Ayni ad baska kullanicida serbesttir.
    assert _create(env, headers=MEHMET, name="A").status_code == 201
    assert _create(env, headers=MEHMET, name="X", initial_cash=500).status_code == 422
    bad = _create(
        env, headers=MEHMET, name="Y", kind="STRATEGY", config={"entry_score": 60, "exit_score": 70}
    )
    assert bad.status_code == 422


def test_other_users_portfolio_is_invisible_everywhere(env):
    portfolio_id = _create(env).json()["id"]
    client = env["client"]
    for method, path in [
        ("get", ""),
        ("patch", ""),
        ("delete", ""),
        ("get", "/positions"),
        ("get", "/trades"),
        ("get", "/trades.csv"),
        ("get", "/performance"),
        ("get", "/risk"),
        ("get", "/orders"),
        ("post", "/orders"),
        ("delete", "/orders/1"),
    ]:
        kwargs = {"headers": MEHMET}
        if method in {"patch", "post"}:
            kwargs["json"] = (
                {"ticker": "THYAO", "side": "BUY", "amount": 5000}
                if path == "/orders"
                else {"name": "Ele geçir"}
            )
        response = getattr(client, method)(f"/api/me/portfolios/{portfolio_id}{path}", **kwargs)
        assert response.status_code == 404, (method, path, response.status_code)
    assert client.get(f"/api/me/portfolios/{portfolio_id}", headers=AYSE).status_code == 200


def test_public_paper_api_only_shows_model_portfolio(env):
    user_portfolio = _create(env).json()["id"]
    client = env["client"]
    public = client.get("/api/paper/portfolios").json()
    assert [row["name"] for row in public] == ["Ana Paper Portföy"]
    for path in ["", "/positions", "/trades", "/performance", "/risk", "/trades.csv"]:
        assert client.get(f"/api/paper/portfolios/{user_portfolio}{path}").status_code == 404
    assert client.get(f"/api/paper/portfolios/{public[0]['id']}/risk").status_code == 200


def test_manual_orders_validation_reservation_and_cancel(env):
    client = env["client"]
    portfolio_id = _create(env).json()["id"]
    strategy_id = _create(env, name="Strateji", kind="STRATEGY").json()["id"]
    orders = f"/api/me/portfolios/{portfolio_id}/orders"

    not_manual = client.post(
        f"/api/me/portfolios/{strategy_id}/orders",
        headers=AYSE,
        json={"ticker": "THYAO", "side": "BUY", "amount": 5000},
    )
    assert not_manual.json()["detail"]["code"] == "not_manual"
    unknown = client.post(
        orders, headers=AYSE, json={"ticker": "YOKYOK", "side": "BUY", "amount": 5000}
    )
    assert unknown.json()["detail"]["code"] == "unknown_ticker"
    inactive = client.post(
        orders, headers=AYSE, json={"ticker": "ESKI", "side": "BUY", "amount": 5000}
    )
    assert inactive.json()["detail"]["code"] == "unknown_ticker"
    both = client.post(
        orders, headers=AYSE, json={"ticker": "THYAO", "side": "BUY", "amount": 5000, "quantity": 3}
    )
    assert both.status_code == 422
    assert (
        client.post(
            orders, headers=AYSE, json={"ticker": "THYAO", "side": "SELL", "amount": 5000}
        ).status_code
        == 422
    )

    no_shares = client.post(
        orders, headers=AYSE, json={"ticker": "THYAO", "side": "SELL", "quantity": 1}
    )
    assert no_shares.json()["detail"]["code"] == "insufficient_shares"
    with Session(env["db"]) as session:
        session.add(
            PaperPosition(
                portfolio_id=portfolio_id,
                ticker="THYAO",
                quantity=10,
                average_cost=100,
                last_price=100,
                market_value=1000,
                unrealized_pnl=0,
            )
        )
        session.commit()
    first = client.post(
        orders,
        headers=AYSE,
        json={"ticker": "thyao", "side": "SELL", "quantity": 6, "client_order_id": "form-1"},
    )
    assert first.status_code == 201 and first.json()["status"] == "PENDING"
    assert first.json()["ticker"] == "THYAO" and first.json()["not_before"]
    again = client.post(
        orders,
        headers=AYSE,
        json={"ticker": "THYAO", "side": "SELL", "quantity": 6, "client_order_id": "form-1"},
    )
    assert again.json()["id"] == first.json()["id"]
    reserved = client.post(
        orders, headers=AYSE, json={"ticker": "THYAO", "side": "SELL", "quantity": 5}
    )
    assert reserved.json()["detail"]["code"] == "insufficient_shares"
    assert "bekleyen" in reserved.json()["detail"]["message"]
    buy = client.post(orders, headers=AYSE, json={"ticker": "ASELS", "side": "BUY", "amount": 5000})
    assert buy.status_code == 201

    listing = client.get("/api/me/portfolios", headers=AYSE).json()
    assert next(row for row in listing if row["id"] == portfolio_id)["pending_orders"] == 2

    order_id = first.json()["id"]
    cancelled = client.delete(f"{orders}/{order_id}", headers=AYSE)
    assert cancelled.json()["status"] == "CANCELLED"
    assert client.delete(f"{orders}/{order_id}", headers=AYSE).status_code == 409
    assert [row["status"] for row in client.get(orders, headers=AYSE).json()] == [
        "PENDING",
        "CANCELLED",
    ]

    paused = client.patch(
        f"/api/me/portfolios/{portfolio_id}", headers=AYSE, json={"status": "PAUSED"}
    )
    assert paused.json()["status"] == "PAUSED"
    blocked = client.post(
        orders, headers=AYSE, json={"ticker": "ASELS", "side": "BUY", "amount": 5000}
    )
    assert blocked.json()["detail"]["code"] == "paused"


def test_settings_update_and_delete(env):
    client = env["client"]
    strategy_id = _create(env, name="Strateji", kind="STRATEGY").json()["id"]
    manual_id = _create(env, name="Elle").json()["id"]
    updated = client.patch(
        f"/api/me/portfolios/{strategy_id}",
        headers=AYSE,
        json={"name": "Yeni ad", "config": {"entry_score": 85, "exit_score": 60}},
    )
    assert updated.json()["name"] == "Yeni ad" and updated.json()["config"]["entry_score"] == 85
    risk = client.get(f"/api/me/portfolios/{strategy_id}/risk", headers=AYSE).json()
    assert risk["rules"]["stop_loss_pct"] == 15
    manual_risk = client.get(f"/api/me/portfolios/{manual_id}/risk", headers=AYSE).json()
    assert manual_risk["rules"]["stop_loss_pct"] == 0
    assert manual_risk["rules"]["max_position_weight_pct"] == 0
    rejected = client.patch(
        f"/api/me/portfolios/{manual_id}", headers=AYSE, json={"config": {"entry_score": 80}}
    )
    assert rejected.json()["detail"]["code"] == "not_strategy"
    assert client.delete(f"/api/me/portfolios/{manual_id}", headers=AYSE).status_code == 204
    assert client.get(f"/api/me/portfolios/{manual_id}", headers=AYSE).status_code == 404


def test_templates_endpoint(env):
    templates = env["client"].get("/api/me/portfolios/templates").json()
    assert [row["key"] for row in templates] == ["model", "temkinli", "agresif"]
