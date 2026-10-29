"""Manuel emir kararlari, emir gunu hesabi ve strateji ayarlari (saf fonksiyonlar)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.paper.risk import RiskConfig
from app.paper.service import (
    DEFAULT_PARAMS,
    ORDER_MAX_WAIT_DAYS,
    decide_manual_order,
    entry_slots,
    order_not_before,
    portfolio_strategy,
    select_entry_signals,
)
from app.paper.strategy import TEMPLATES, StrategyConfig

TZ = "Europe/Istanbul"


def _order(**overrides):
    values = {
        "ticker": "THYAO",
        "side": "BUY",
        "quantity": None,
        "amount": Decimal(10_000),
        "close": Decimal(100),
        "day_change": Decimal(1),
        "held": Decimal(0),
        "cash": Decimal(50_000),
        "waited_days": 0,
    }
    return decide_manual_order(**{**values, **overrides})


def test_order_day_moves_after_close_and_over_weekends():
    # 2026-10-28 Carsamba; Istanbul UTC+3.
    assert order_not_before(datetime(2026, 10, 28, 14, 59, tzinfo=UTC), TZ) == date(2026, 10, 28)
    assert order_not_before(datetime(2026, 10, 28, 15, 0, tzinfo=UTC), TZ) == date(2026, 10, 29)
    assert order_not_before(datetime(2026, 10, 30, 16, 0, tzinfo=UTC), TZ) == date(2026, 11, 2)
    assert order_not_before(datetime(2026, 10, 31, 9, 0, tzinfo=UTC), TZ) == date(2026, 11, 2)


def test_buy_by_amount_uses_whole_shares_with_slippage_and_fee():
    decision = _order()
    assert decision.action == "fill"
    plan = decision.plan
    assert plan.quantity == 99 and plan.price == Decimal("100.05")
    assert plan.gross_amount + plan.fee_amount <= Decimal(10_000)


def test_buy_rejections_and_limit_up_wait():
    assert _order(amount=Decimal(500)).action == "reject"
    assert _order(amount=None, quantity=Decimal(1000)).reason == "Yetersiz nakit."
    assert _order(amount=None, quantity=Decimal(5)).action == "reject"  # 1.000 TL altinda
    assert _order(day_change=Decimal("9.8")).action == "hold"
    expired = _order(day_change=Decimal("9.8"), waited_days=ORDER_MAX_WAIT_DAYS)
    assert expired.action == "reject" and "tavanda" in expired.reason


def test_sell_requires_holdings_and_waits_at_limit_down():
    sell = {"side": "SELL", "amount": None, "quantity": Decimal(10)}
    assert _order(**sell).reason == "Portföyde bu hisse yok."
    assert _order(**sell, held=Decimal(5)).action == "reject"
    filled = _order(**sell, held=Decimal(10))
    assert filled.action == "fill" and filled.plan.price == Decimal("99.95")
    assert _order(**sell, held=Decimal(10), day_change=Decimal(-10)).action == "hold"


def test_untraded_ticker_waits_then_expires():
    assert _order(close=None).action == "hold"
    assert _order(close=None, waited_days=ORDER_MAX_WAIT_DAYS).action == "reject"


def test_strategy_config_validation_and_templates():
    with pytest.raises(ValidationError, match="Çıkış skoru"):
        StrategyConfig(entry_score=70, exit_score=70)
    with pytest.raises(ValidationError, match="%100"):
        StrategyConfig(max_positions=20, max_position_weight_pct=10)
    for template in TEMPLATES.values():
        assert template.config.max_positions * template.config.max_position_weight_pct <= 100
    model = TEMPLATES["model"].config
    assert model.params() == DEFAULT_PARAMS
    assert str(model.params().entry_score) == "75"
    assert model.risk() == RiskConfig(
        stop_loss_pct=Decimal(15),
        max_position_weight=Decimal("0.1"),
        max_sector_weight=Decimal("0.3"),
        rebalance_enabled=True,
    )


def test_portfolio_strategy_uses_own_config_or_model_rules():
    model_risk = RiskConfig(stop_loss_pct=Decimal(7))
    model = SimpleNamespace(kind="STRATEGY", config=None)
    assert portfolio_strategy(model, model_risk) == (DEFAULT_PARAMS, model_risk)
    custom = SimpleNamespace(kind="STRATEGY", config=TEMPLATES["temkinli"].config.model_dump())
    params, risk = portfolio_strategy(custom, model_risk)
    assert params.entry_score == 80 and risk.stop_loss_pct == 10 and risk.trailing_stop_pct == 10


def test_entry_selection_and_slots_follow_custom_params():
    signals = [
        SimpleNamespace(ticker="AAA", composite_score=82, confidence=0.5, coverage_count=1),
        SimpleNamespace(ticker="BBB", composite_score=78, confidence=0.5, coverage_count=3),
    ]
    strict = TEMPLATES["temkinli"].config.params()
    loose = StrategyConfig(entry_score=70, exit_score=50, min_coverage=1).params()
    assert [row.ticker for row in select_entry_signals(signals, held_tickers=set(), slots=5)] == [
        "BBB"
    ]
    assert select_entry_signals(signals, held_tickers=set(), slots=5, params=strict) == []
    picked = select_entry_signals(signals, held_tickers=set(), slots=5, params=loose)
    assert [row.ticker for row in picked] == ["AAA", "BBB"]
    assert entry_slots(open_count=7, bought_today=0, params=strict) == 1
