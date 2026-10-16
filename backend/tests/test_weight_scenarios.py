"""Agirlik senaryosu raporu testleri."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.signals.accuracy import ComponentObservation, PricePoint, compute_component_power
from app.signals.reports import (
    _SCENARIO_PREFIX,
    WEIGHT_SCENARIOS,
    _scenario_scores,
    scenario_reports,
)
from app.signals.service import ComponentResult, build_composite_signal


def test_scenario_weights_sum_to_one_and_current_matches_live_model():
    for key, _, weights in WEIGHT_SCENARIOS:
        assert sum(weights.values()) == Decimal(1), key
    built = build_composite_signal(
        "THYAO",
        {
            "llm": ComponentResult(Decimal(70), Decimal("0.8"), {}),
            "fundamental": ComponentResult(Decimal(60), Decimal("0.9"), {}),
            "analyst": ComponentResult(Decimal(20), Decimal("0.5"), {}),
        },
        as_of_date=date(2026, 10, 1),
    )
    row = SimpleNamespace(
        component_scores=built["component_scores"],
        confidence=built["confidence"],
        component_confidences=built["evidence"]["confidences"],
    )
    scores = _scenario_scores(row)
    assert abs(scores[_SCENARIO_PREFIX + "current"] - float(built["composite_score"])) <= 0.01
    # Analist dusuk puan veriyor: analist agirligi azaldikca skor yukselir.
    assert scores[_SCENARIO_PREFIX + "analyst_off"] > scores[_SCENARIO_PREFIX + "current"]


def test_scenario_reports_rank_power_per_scenario():
    start = date(2026, 1, 5)
    days = [start + timedelta(days=offset) for offset in range(12)]
    observations, prices = [], []
    for index in range(25):
        ticker = f"T{index:02d}"
        for day_index, day in enumerate(days):
            # Temel zayif ama dogru sinyal; analist guclu ve ters (yuksek skor -> dusuk
            # getiri). Canli agirliklarda analist baskin cikar, siralama tersine doner.
            row = SimpleNamespace(
                component_scores={
                    "fundamental": float(40 + index),
                    "analyst": float(100 - index * 4),
                },
                confidence=Decimal("0.8"),
                component_confidences=None,
            )
            observations.append(ComponentObservation(ticker, day, _scenario_scores(row)))
            prices.append(
                PricePoint(ticker, day, Decimal(100) * (1 + Decimal(index) / 1000) ** day_index)
            )
    power = compute_component_power(
        observations,
        prices,
        horizons=(5,),
        components=tuple(_SCENARIO_PREFIX + key for key, _, _ in WEIGHT_SCENARIOS),
    )
    rows = {row["key"]: row for row in scenario_reports(power)}
    assert set(rows) == {key for key, _, _ in WEIGHT_SCENARIOS}
    assert rows["current"]["mean_ic"] < 0 < rows["analyst_off"]["mean_ic"]
    assert rows["analyst_off"]["weights"]["analyst"] == 0
    assert rows["current"]["label"] == "Canlı model (v3)"
