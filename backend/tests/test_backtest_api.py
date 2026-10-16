"""Backtest API sozlesmesi ve istek dogrulama testleri."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.backtest.service import backtest_status
from app.main import app
from app.schemas.backtest import BacktestCreate


def test_backtest_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/backtests" in paths
    assert "/api/backtests/{run_id}" in paths


def test_backtest_request_defaults_are_safe_and_explicit():
    request = BacktestCreate(start_date=date(2025, 1, 1), end_date=date(2026, 1, 1))

    assert request.entry_score == 75
    assert request.exit_score == 55
    assert request.strategy == "threshold"
    assert request.component_weights is None
    assert request.max_positions == 10
    assert request.max_position_weight == 0.10
    assert request.fee_rate == 0.001
    assert request.slippage_rate == 0.0005


def test_backtest_rejects_invalid_dates_and_thresholds():
    with pytest.raises(ValidationError, match="end_date"):
        BacktestCreate(start_date=date(2026, 1, 2), end_date=date(2026, 1, 1))

    with pytest.raises(ValidationError, match="exit_score"):
        BacktestCreate(
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            entry_score=40,
            exit_score=40,
        )


def test_backtest_marks_all_unexecutable_signals_as_insufficient_data():
    assert (
        backtest_status(signal_count=176, point_count=22, skipped_signal_count=176)
        == "INSUFFICIENT_DATA"
    )
    assert (
        backtest_status(signal_count=176, point_count=22, skipped_signal_count=175) == "COMPLETED"
    )


def test_backtest_validates_basket_and_component_weights():
    period = {"start_date": date(2025, 1, 1), "end_date": date(2026, 1, 1)}
    with pytest.raises(ValidationError, match="basket_keep"):
        BacktestCreate(**period, strategy="basket", basket_size=20, basket_keep=10)
    with pytest.raises(ValidationError):
        BacktestCreate(**period, component_weights={"sentiment": 0.5})
    with pytest.raises(ValidationError, match="pozitif"):
        BacktestCreate(**period, component_weights={"llm": 0, "analyst": 0})
    request = BacktestCreate(**period, strategy="basket", component_weights={"analyst": 0.1})
    assert request.component_weights == {"analyst": 0.1}


def test_robustness_reports_shifted_starts_against_benchmark():
    from decimal import Decimal

    from app.backtest import BacktestConfig, BacktestPrice, BacktestSignal
    from app.backtest.service import run_with_robustness

    days = [date(2026, 1, day) for day in range(1, 31) if date(2026, 1, day).weekday() < 5]
    signals = [BacktestSignal("AAA", day, Decimal(80), Decimal("0.9"), 4) for day in days]
    prices = [
        BacktestPrice("AAA", day, Decimal(100 + index), Decimal("1e9"))
        for index, day in enumerate(days)
    ]
    benchmark = [(day, Decimal(1000)) for day in days]
    result, robustness = run_with_robustness(
        signals,
        prices,
        config=BacktestConfig(strategy="basket", basket_size=1, basket_keep=1, rebalance_days=5),
        benchmark=benchmark,
        start_date=days[0],
        end_date=days[-1],
    )
    assert result.points
    assert robustness["shifts_trading_days"] == [0, 2, 4, 6, 8]
    assert [run["start_date"] for run in robustness["runs"]] == [
        days[shift].isoformat() for shift in (0, 2, 4, 6, 8)
    ]
    # Endeks yatay, hisse yukseliyor: her kosu endeksi gecer.
    assert robustness["beat_benchmark_runs"] == 5
    assert robustness["excess_min_pct"] > 0
