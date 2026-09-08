"""Sinyal dogruluk raporu (ileri getiri/isabet orani) testleri."""

from datetime import date
from decimal import Decimal

from app.signals.accuracy import (
    PricePoint,
    SignalObservation,
    compute_signal_accuracy,
)


def signal(ticker: str, day: int, label: str, score: str = "80") -> SignalObservation:
    return SignalObservation(ticker, date(2026, 1, day), Decimal(score), label)


def price(ticker: str, day: int, close: str) -> PricePoint:
    return PricePoint(ticker, date(2026, 1, day), Decimal(close))


def stat(stats, horizon: int, label: str):
    return next(s for s in stats if s.horizon == horizon and s.label == label)


def _consecutive_prices(ticker: str, start_day: int, closes: list[str]) -> list[PricePoint]:
    return [price(ticker, start_day + i, close) for i, close in enumerate(closes)]


def test_positive_label_with_rising_price_counts_as_a_hit():
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "POSITIVE")],
        _consecutive_prices("THYAO", 2, ["100", "100", "101", "102", "103", "104", "110"]),
        horizons=(5,),
    )

    result = stat(stats, 5, "POSITIVE")
    assert result.observation_count == 1
    assert result.hit_rate_pct == 100
    assert result.average_return_pct == 10


def test_negative_label_with_rising_price_counts_as_a_miss():
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "NEGATIVE")],
        _consecutive_prices("THYAO", 2, ["100", "100", "101", "102", "103", "104", "110"]),
        horizons=(5,),
    )

    result = stat(stats, 5, "NEGATIVE")
    assert result.hit_rate_pct == 0


def test_neutral_label_is_excluded_from_hit_rate_but_included_in_average():
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "NEUTRAL")],
        _consecutive_prices("THYAO", 2, ["100", "100", "101", "102", "103", "104", "105"]),
        horizons=(5,),
    )

    result = stat(stats, 5, "NEUTRAL")
    assert result.hit_rate_pct is None
    assert result.average_return_pct == 5


def test_signal_without_any_future_price_is_excluded():
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "POSITIVE")],
        [price("THYAO", 2, "100")],
        horizons=(5,),
    )

    result = stat(stats, 5, "POSITIVE")
    assert result.observation_count == 0
    assert result.average_return_pct is None
    assert result.hit_rate_pct is None


def test_short_horizon_contributes_even_when_long_horizon_data_is_missing():
    prices = [price("THYAO", day, "100") for day in range(2, 9)]  # gunler 2..8
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "POSITIVE")],
        prices,
        horizons=(3, 20),
    )

    assert stat(stats, 3, "POSITIVE").observation_count == 1
    assert stat(stats, 20, "POSITIVE").observation_count == 0


def test_signal_day_close_is_not_used_as_entry_to_avoid_lookahead_bias():
    # Sinyal gunu (2 Ocak) kapanisi 200 olsa da baz fiyat SONRAKI gun (3
    # Ocak, 100) olmali; aksi halde ayni gunun kapanisi sizmis olur.
    stats = compute_signal_accuracy(
        [signal("THYAO", 2, "POSITIVE")],
        [price("THYAO", 2, "200")]
        + _consecutive_prices("THYAO", 3, ["100", "101", "102", "103", "104", "110"]),
        horizons=(5,),
    )

    assert stat(stats, 5, "POSITIVE").average_return_pct == 10


def test_multiple_signals_average_correctly():
    stats = compute_signal_accuracy(
        [signal("AAAA", 2, "POSITIVE"), signal("BBBB", 2, "POSITIVE")],
        _consecutive_prices("AAAA", 2, ["100", "100", "101", "102", "103", "104", "120"])
        + _consecutive_prices("BBBB", 2, ["100", "100", "100", "100", "100", "100", "100"]),
        horizons=(5,),
    )

    result = stat(stats, 5, "POSITIVE")
    assert result.observation_count == 2
    assert result.average_return_pct == 10
    assert result.hit_rate_pct == 50
