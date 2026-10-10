"""Bilesik skor motorunun agsiz, deterministik testleri."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.signals.accuracy import DEFAULT_HORIZONS, SIGNAL_LABELS
from app.signals.service import (
    ComponentResult,
    build_composite_signal,
    score_analyst,
    score_fundamental,
    score_llm_evaluations,
    score_momentum,
    signal_label,
)


def test_signal_label_boundaries_are_stable():
    assert signal_label(75) == "VERY_POSITIVE"
    assert signal_label(60) == "POSITIVE"
    assert signal_label(40) == "NEUTRAL"
    assert signal_label(25) == "NEGATIVE"
    assert signal_label(24.99) == "VERY_NEGATIVE"


def test_composite_renormalizes_missing_components_instead_of_counting_zero():
    components = {
        "fundamental": ComponentResult(Decimal(80), Decimal(1), {"id": 1}),
        "analyst": ComponentResult(Decimal(60), Decimal("0.75"), {"id": 2}),
    }

    result = build_composite_signal("THYAO", components, as_of_date=date(2026, 9, 7))

    assert result is not None
    # Ham 71,2; guven 0,445 < 0,60 oldugundan 50'ye dogru cekilir.
    assert result["evidence"]["raw_score"] == 71.2
    assert result["composite_score"] == Decimal("65.72")
    assert result["signal_label"] == "POSITIVE"
    assert result["coverage_count"] == 2
    assert result["component_weights"] == {"fundamental": 0.56, "analyst": 0.44}
    assert result["confidence"] == Decimal("0.44500")


def test_low_confidence_score_is_pulled_toward_neutral():
    weak = {
        "llm": ComponentResult(Decimal(90), Decimal("0.2"), {}),
        "analyst": ComponentResult(Decimal(90), Decimal("0.2"), {}),
    }
    strong = {
        "llm": ComponentResult(Decimal(80), Decimal(1), {}),
        "fundamental": ComponentResult(Decimal(80), Decimal(1), {}),
        "analyst": ComponentResult(Decimal(80), Decimal(1), {}),
    }

    weak_result = build_composite_signal("AAA", weak, as_of_date=date(2026, 9, 7))
    strong_result = build_composite_signal("BBB", strong, as_of_date=date(2026, 9, 7))

    assert weak_result["evidence"]["raw_score"] == 90.0
    assert weak_result["composite_score"] < strong_result["composite_score"]
    assert strong_result["composite_score"] == Decimal("80.00")


def test_fund_flow_is_not_a_composite_component():
    components = {
        "analyst": ComponentResult(Decimal(90), Decimal(1), {}),
        "fund_flow": ComponentResult(Decimal(47), Decimal(1), {}),
    }
    assert build_composite_signal("GWIND", components, as_of_date=date(2026, 9, 7)) is None


def test_stale_analyst_consensus_loses_confidence():
    base = {
        "id": 5,
        "recommendation_score": Decimal(100),
        "institution_count": 8,
        "as_of_date": date(2026, 9, 7),
        "implied_upside_pct": None,
    }
    fresh = score_analyst(SimpleNamespace(**base, average_age_days=Decimal(0)))
    stale = score_analyst(SimpleNamespace(**base, average_age_days=Decimal(120)))

    assert fresh.confidence == Decimal(1)
    assert stale.confidence == Decimal("0.5")


def test_single_component_is_not_published_as_composite_signal():
    components = {"analyst": ComponentResult(Decimal(90), Decimal(1), {})}
    assert build_composite_signal("ASELS", components, as_of_date=date(2026, 9, 7)) is None


def test_llm_score_prefers_tier_two_for_same_source_document():
    now = datetime(2026, 9, 7, 12, tzinfo=UTC)
    base = {
        "id": 10,
        "source_type": "news",
        "source_id": 99,
        "ticker_codes": ["THYAO"],
        "relevance_score": 100,
        "impact_score": 80,
        "confidence": Decimal(1),
        "created_at": now - timedelta(hours=1),
        "completed_at": now - timedelta(hours=1),
    }
    tier_one = SimpleNamespace(**base, tier=1, sentiment_score=Decimal(-1))
    tier_two = SimpleNamespace(
        **{**base, "id": 11}, tier=2, sentiment_score=Decimal("0.8")
    )

    result = score_llm_evaluations([tier_one, tier_two], "THYAO", now=now)

    assert result is not None
    assert result.score == Decimal(82)
    assert result.evidence == {"evaluation_ids": [11], "document_count": 1}


def test_component_adapters_bound_scores_and_expose_evidence():
    fundamental = score_fundamental(
        SimpleNamespace(
            id=4,
            fundamental_score=Decimal("83.2"),
            data_completeness=11,
            year=2026,
            period=6,
        )
    )
    analyst = score_analyst(
        SimpleNamespace(
            id=5,
            recommendation_score=Decimal(75),
            institution_count=6,
            as_of_date=date(2026, 9, 7),
            implied_upside_pct=Decimal("20.5"),
        )
    )

    assert fundamental is not None and fundamental.score == Decimal("83.2")
    assert fundamental.confidence == Decimal(1)
    assert analyst is not None and analyst.confidence == Decimal("0.75")
    assert analyst.score == Decimal("71.3125")


def test_signal_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/signals" in paths
    assert "/api/signals/{ticker}" in paths
    assert "/api/signals/accuracy" in paths


def test_accuracy_endpoint_executes_query_path_and_returns_horizon_shape():
    """"/accuracy" literal segmenti /{ticker} route'undan once eslesmeli."""

    class _Rows:
        def all(self):
            return []

    class _Session:
        async def execute(self, statement):
            return _Rows()

    async def override_db():
        yield _Session()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/signals/accuracy")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    # Bos girdiyle bile her (vade, etiket) kombinasyonu icin bir satir doner
    # (compute_signal_accuracy hep tam matris uretir) — bu, yanitin
    # CompositeSignalOut degil SignalHorizonStatOut sekli oldugunu kanitlar.
    payload = response.json()
    assert len(payload) == len(DEFAULT_HORIZONS) * len(SIGNAL_LABELS)
    assert {"horizon", "label", "observation_count", "average_return_pct", "hit_rate_pct"} <= set(
        payload[0]
    )


def test_signal_list_endpoint_executes_query_path():
    class _Rows:
        def all(self):
            return []

    class _Session:
        async def scalar(self, statement):
            return date(2026, 9, 7)

        async def scalars(self, statement):
            return _Rows()

    async def override_db():
        yield _Session()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/signals?limit=5")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []


def _series(start: date, values: list[float]) -> list[tuple[date, Decimal]]:
    return [(start + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(values)]


def test_momentum_scores_relative_to_benchmark_not_absolute_return():
    start = date(2026, 6, 1)
    # Hisse 61 gunde %0, endeks %-20: goreli +20 puan (hem 20g hem 60g'de pozitif).
    closes = _series(start, [100.0] * 61)
    index = _series(start, [1000 - i * (200 / 60) for i in range(61)])
    as_of = start + timedelta(days=60)

    result = score_momentum(closes, index, as_of_date=as_of)

    assert result is not None
    assert result.score > 50
    assert result.confidence == Decimal(1)
    assert result.evidence["relative_60d_pct"] > 0


def test_momentum_requires_enough_and_fresh_prices():
    start = date(2026, 6, 1)
    index = _series(start, [1000.0] * 61)
    assert score_momentum(_series(start, [100.0] * 15), index, as_of_date=start + timedelta(days=14)) is None
    stale = _series(start, [100.0] * 30)
    assert score_momentum(stale, index, as_of_date=start + timedelta(days=45)) is None


def test_momentum_ignores_prices_after_as_of_date():
    start = date(2026, 6, 1)
    index = _series(start, [1000.0] * 40)
    flat_then_spike = _series(start, [100.0] * 30 + [300.0] * 10)

    result = score_momentum(flat_then_spike, index, as_of_date=start + timedelta(days=29))

    assert result is not None
    assert result.score == Decimal(50)
