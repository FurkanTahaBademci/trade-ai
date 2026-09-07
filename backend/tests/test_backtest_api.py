"""Backtest API sozlesmesi ve istek dogrulama testleri."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.backtest import BacktestCreate


def test_backtest_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/backtests" in paths
    assert "/api/backtests/{run_id}" in paths


def test_backtest_request_defaults_are_safe_and_explicit():
    request = BacktestCreate(start_date=date(2025, 1, 1), end_date=date(2026, 1, 1))

    assert request.entry_score == 75
    assert request.exit_score == 40
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
