import pytest

from app.core.valuation import price_multiple, trailing_net_income


def test_annual_period_is_already_twelve_months():
    assert trailing_net_income(year=2025, period=12, net_income=120.0, history={}) == (
        120.0,
        "annual",
    )


def test_interim_period_uses_prior_year_to_complete_twelve_months():
    # 2026/6 kumulatif 70; 2025 yillik 100, 2025/6 kumulatif 40 -> TTM 130
    history = {(2025, 12): 100.0, (2025, 6): 40.0}
    assert trailing_net_income(year=2026, period=6, net_income=70.0, history=history) == (
        130.0,
        "ttm",
    )


def test_interim_period_without_prior_year_is_annualized():
    ttm, basis = trailing_net_income(year=2026, period=3, net_income=25.0, history={})
    assert ttm == pytest.approx(100.0)
    assert basis == "annualized"


def test_missing_net_income_has_no_ttm():
    assert trailing_net_income(year=2026, period=9, net_income=None, history={}) == (None, None)


def test_price_multiple_rejects_losses_and_missing_values():
    assert price_multiple(1_000.0, 100.0) == pytest.approx(10.0)
    assert price_multiple(1_000.0, -50.0) is None
    assert price_multiple(1_000.0, 0.0) is None
    assert price_multiple(None, 100.0) is None
    assert price_multiple(0.0, 100.0) is None
