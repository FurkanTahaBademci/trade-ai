"""Bilesik skor motorunun agsiz, deterministik testleri."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.signals.service import (
    ComponentResult,
    build_composite_signal,
    score_analyst,
    score_fund_flow,
    score_fundamental,
    score_llm_evaluations,
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
    assert result["composite_score"] == Decimal("70.91")
    assert result["signal_label"] == "POSITIVE"
    assert result["coverage_count"] == 2
    assert result["component_weights"] == {"fundamental": 0.5455, "analyst": 0.4545}
    assert result["confidence"] < Decimal(1)


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
    flow = score_fund_flow(
        SimpleNamespace(
            id=6,
            total_aum=Decimal(1000),
            estimated_stock_flow=Decimal(5),
            positive_flow_pct=Decimal(60),
            flow_observation_count=8,
            fund_count=10,
            date=date(2026, 9, 7),
        ),
        as_of_date=date(2026, 9, 7),
    )

    assert fundamental is not None and fundamental.score == Decimal("83.2")
    assert fundamental.confidence == Decimal(1)
    assert analyst is not None and analyst.confidence == Decimal("0.75")
    assert analyst.score == Decimal("71.3125")
    assert flow is not None and flow.score == Decimal(88)
    assert flow.confidence == Decimal("0.8")


def test_signal_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/signals" in paths
    assert "/api/signals/{ticker}" in paths


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
