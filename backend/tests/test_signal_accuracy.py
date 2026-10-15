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


def test_excess_return_subtracts_benchmark_over_same_window():
    # Hisse %-5, endeks %-10: mutlak yon isabeti yok ama endeksi yendi.
    prices = _consecutive_prices("THYAO", 2, ["100", "100", "99", "98", "97", "96", "95"])
    benchmark = [(date(2026, 1, 2 + i), Decimal(v)) for i, v in enumerate(
        ["1000", "1000", "980", "960", "940", "920", "900"]
    )]

    result = stat(
        compute_signal_accuracy(
            [signal("THYAO", 2, "POSITIVE")], prices, horizons=(5,), benchmark=benchmark
        ),
        5,
        "POSITIVE",
    )

    assert result.average_return_pct == -5
    assert result.hit_rate_pct == 0
    assert result.average_excess_pct == 5
    assert result.beat_rate_pct == 100


def test_excess_fields_are_empty_without_benchmark():
    result = stat(
        compute_signal_accuracy(
            [signal("THYAO", 2, "POSITIVE")],
            _consecutive_prices("THYAO", 2, ["100"] * 7),
            horizons=(5,),
        ),
        5,
        "POSITIVE",
    )

    assert result.average_excess_pct is None
    assert result.beat_rate_pct is None


def test_weekend_signals_sharing_one_entry_close_are_counted_once():
    # 2, 3, 4 Ocak skorlarinin hepsi 5 Ocak kapanisindan girer; en guncel olan sayilir.
    stats = compute_signal_accuracy(
        [signal("AAAA", 2, "NEGATIVE"), signal("AAAA", 3, "NEGATIVE"), signal("AAAA", 4, "POSITIVE")],
        [price("AAAA", 2, "100"), *_consecutive_prices("AAAA", 5, ["100", "101", "110"])],
        horizons=(2,),
    )
    assert stat(stats, 2, "POSITIVE").observation_count == 1
    assert stat(stats, 2, "NEGATIVE").observation_count == 0


def test_spearman_handles_order_and_ties():
    from app.signals.accuracy import spearman

    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert abs(spearman([1, 2, 2, 3], [1, 2, 3, 4]) - 0.9486832980505138) < 1e-9


def test_component_power_ranks_forward_returns_per_day():
    from app.signals.accuracy import ComponentObservation, compute_component_power

    observations, prices = [], []
    for index in range(25):
        ticker = f"T{index:02d}"
        # Momentum skoru yuksek olan daha cok kazanir; analist skoru tersine isaret eder.
        observations.append(
            ComponentObservation(
                ticker,
                date(2026, 1, 2),
                {"composite": index, "momentum": index, "analyst": 100 - index},
            )
        )
        prices += _consecutive_prices(ticker, 2, ["100", "100", str(100 + index)])

    power = {
        (row.component, row.horizon): row
        for row in compute_component_power(observations, prices, horizons=(1, 5), min_cross_section=20)
    }

    assert power[("momentum", 1)].mean_ic == 1
    assert power[("momentum", 1)].positive_ic_pct == 100
    assert power[("momentum", 1)].spread_pct > 0
    assert power[("analyst", 1)].mean_ic == -1
    assert power[("llm", 1)].days == 0 and power[("llm", 1)].mean_ic is None
    # 5 gunluk vade icin gelecek fiyat yok.
    assert power[("momentum", 5)].days == 0
