"""Karsilastirma ucundaki F/K, PD/DD, ROE ve net marjin tek tabandan gelmesi."""

import pytest

from app.api.routers.markets import compare_valuation, compare_valuation_empty


def _valuation(**overrides):
    params = {
        "year": 2026,
        "period": 3,
        "net_income": -500.0,
        "revenue": 5_000.0,
        "equity": 10_000.0,
        "market_cap": 6_000.0,
        "net_income_history": {(2025, 12): 1_000.0, (2025, 3): -400.0},
        "revenue_history": {(2025, 12): 24_000.0, (2025, 3): 4_000.0},
    }
    params.update(overrides)
    return compare_valuation(**params)


def test_seasonal_quarter_loss_uses_ttm_for_every_ratio():
    # Ilk ceyrek zarari (-500) yilliklandirilsa ROE -%20 cikar; son 12 ay kari
    # ise -500 + 1000 - (-400) = 900 pozitiftir. F/K, ROE ve marj ayni tabanda.
    result = _valuation()
    assert result["ttm_net_income_try"] == pytest.approx(900.0)
    assert result["ttm_revenue_try"] == pytest.approx(25_000.0)
    assert result["pe_ratio"] == pytest.approx(6.67)
    assert result["pb_ratio"] == pytest.approx(0.6)
    assert result["roe_pct"] == pytest.approx(9.0)
    assert result["net_margin_pct"] == pytest.approx(3.6)
    assert result["ttm_basis"] == "ttm"
    assert result["fundamental_period"] == "2026/3"
    # Tutarlilik: F/K x ROE = PD/DD
    assert result["pe_ratio"] * result["roe_pct"] / 100 == pytest.approx(
        result["pb_ratio"], rel=1e-2
    )


def test_trailing_loss_hides_pe_but_keeps_negative_roe_and_margin():
    result = _valuation(net_income_history={(2025, 12): -2_000.0, (2025, 3): -100.0})
    # -500 - 2000 + 100 = -2400
    assert result["ttm_net_income_try"] == pytest.approx(-2_400.0)
    assert result["pe_ratio"] is None
    assert result["pb_ratio"] == pytest.approx(0.6)
    assert result["roe_pct"] == pytest.approx(-24.0)
    assert result["net_margin_pct"] < 0


def test_negative_equity_hides_pb_and_roe():
    result = _valuation(equity=-1_000.0)
    assert result["pb_ratio"] is None
    assert result["roe_pct"] is None
    assert result["pe_ratio"] is not None


def test_annual_period_uses_reported_figures():
    result = _valuation(period=12, net_income=1_200.0, revenue=24_000.0)
    assert result["ttm_basis"] == "annual"
    assert result["roe_pct"] == pytest.approx(12.0)
    assert result["net_margin_pct"] == pytest.approx(5.0)
    assert result["pe_ratio"] == pytest.approx(5.0)


def test_missing_prior_year_falls_back_to_annualized():
    result = _valuation(
        period=6, net_income=600.0, revenue=10_000.0, net_income_history={}, revenue_history={}
    )
    assert result["ttm_basis"] == "annualized"
    assert result["ttm_net_income_try"] == pytest.approx(1_200.0)
    assert result["net_margin_pct"] == pytest.approx(6.0)


def test_zero_market_cap_hides_multiples():
    result = _valuation(market_cap=0.0)
    assert result["pe_ratio"] is None
    assert result["pb_ratio"] is None
    assert result["roe_pct"] == pytest.approx(9.0)


def test_empty_shape_matches_full_shape():
    assert set(compare_valuation_empty()) == set(_valuation())
    assert all(v is None for v in compare_valuation_empty().values())
