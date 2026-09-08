"""Gercek SQL sorgulariyla sayfa siniri ve filtre izolasyonunu dogrula."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routers.backtests import list_run_trades
from app.models import BacktestRunTrade


@pytest.fixture
def trade_db():
    engine = create_engine("sqlite://")
    BacktestRunTrade.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            BacktestRunTrade(
                id=i, run_id=1 if i <= 60 else 2,
                ticker="THYAO" if i % 2 else "AKBNK",
                side="BUY" if i % 3 else "SELL",
                signal_date=date(2026, 1, 2), execution_date=date(2026, 1, 5),
                quantity=10, price=100, gross_amount=1000, fee_amount=1,
            ) for i in range(1, 62)
        ])
        session.commit()
        db = AsyncMock()
        db.scalar.return_value = 1
        db.scalars.side_effect = session.scalars
        yield db
    engine.dispose()


async def test_same_day_trades_paginate_without_overlap_or_other_runs(trade_db):
    seen = []
    cursor = None
    sizes = []
    while True:
        rows = await list_run_trades(1, trade_db, before_id=cursor, limit=25)
        sizes.append(len(rows))
        seen.extend(row.id for row in rows)
        if len(rows) < 25:
            break
        cursor = rows[-1].id
    assert sizes == [25, 25, 10]
    assert seen == list(range(60, 0, -1))


async def test_ticker_and_side_filters_apply_on_every_page(trade_db):
    first = await list_run_trades(1, trade_db, ticker="thyao", side="SELL", limit=4)
    second = await list_run_trades(
        1, trade_db, ticker="thyao", side="SELL", before_id=first[-1].id, limit=4
    )
    assert [row.id for row in first + second] == [57, 51, 45, 39, 33, 27, 21, 15]
    assert all(row.ticker == "THYAO" and row.side == "SELL" for row in first + second)


async def test_empty_filter_result_is_not_missing_run(trade_db):
    assert await list_run_trades(1, trade_db, ticker="MISSING") == []
    trade_db.scalar.return_value = None
    with pytest.raises(HTTPException) as error:
        await list_run_trades(999, trade_db)
    assert error.value.status_code == 404
