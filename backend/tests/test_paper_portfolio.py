"""Paper portfoy risk kurallari ve emir planlama testleri."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.main import app
from app.paper.service import (
    FEE_RATE,
    SLIPPAGE_RATE,
    execution_key,
    plan_buy,
    plan_sell,
    select_entry_signals,
)


def test_execution_key_is_deterministic_and_side_specific():
    first = execution_key(1, "THYAO", date(2026, 9, 7), "BUY", "paper-v1")
    second = execution_key(1, "THYAO", date(2026, 9, 7), "BUY", "paper-v1")
    sell = execution_key(1, "THYAO", date(2026, 9, 7), "SELL", "paper-v1")

    assert first == second
    assert first != sell
    assert len(first) == 64


def test_buy_plan_uses_integer_shares_and_never_spends_more_than_cash():
    order = plan_buy(
        "THYAO",
        close_price=Decimal(300),
        budget=Decimal(100_000),
        cash=Decimal(100_000),
    )

    assert order is not None
    assert order.quantity == order.quantity.to_integral_value()
    assert order.price == Decimal(300) * (Decimal(1) + SLIPPAGE_RATE)
    assert order.gross_amount + order.fee_amount <= Decimal(100_000)
    assert order.fee_amount == (order.gross_amount * FEE_RATE).quantize(Decimal("0.0001"))


def test_buy_plan_rejects_too_small_trade():
    assert (
        plan_buy(
            "THYAO",
            close_price=Decimal(300),
            budget=Decimal(500),
            cash=Decimal(500),
        )
        is None
    )


def test_sell_plan_applies_conservative_slippage_and_fee():
    order = plan_sell("THYAO", close_price=Decimal(300), quantity=Decimal(10))

    assert order is not None
    assert order.price == Decimal(300) * (Decimal(1) - SLIPPAGE_RATE)
    assert order.gross_amount == Decimal("2998.5000")
    assert order.fee_amount == Decimal("2.9985")


def test_entry_selection_applies_score_confidence_holdings_and_slot_limit():
    rows = [
        SimpleNamespace(ticker="AAAA", composite_score=80, confidence=0.5, coverage_count=2),
        SimpleNamespace(ticker="BBBB", composite_score=90, confidence=0.5, coverage_count=2),
        SimpleNamespace(ticker="CCCC", composite_score=95, confidence=0.1, coverage_count=4),
        SimpleNamespace(ticker="DDDD", composite_score=70, confidence=0.9, coverage_count=4),
    ]

    selected = select_entry_signals(rows, held_tickers={"BBBB"}, slots=2)

    assert [row.ticker for row in selected] == ["AAAA"]


def test_paper_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/paper/portfolios" in paths
    assert "/api/paper/portfolios/{portfolio_id}/positions" in paths
    assert "/api/paper/portfolios/{portfolio_id}/trades" in paths
    assert "/api/paper/portfolios/{portfolio_id}/performance" in paths
