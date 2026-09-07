"""Analist konsensusu ve TEFAS fon akimi saf fonksiyon testleri."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.collectors.analysts import (
    calculate_consensus,
    parse_aggregator_recommendations,
    parse_isyatirim_recommendations,
)
from app.collectors.fund_flows import (
    aggregate_fund_flows,
    calculate_fund_flows,
    map_tefas_snapshots,
)
from app.core.db import get_db
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_isyatirim_fixture_maps_recommendations():
    html = (FIXTURES / "analysts" / "isyatirim_tracking_sample.html").read_text(encoding="utf-8")
    rows = parse_isyatirim_recommendations(html)

    assert len(rows) == 3
    assert rows[0]["ticker"] == "AEFES"
    assert rows[0]["target_price"] == Decimal("31.43")
    assert rows[0]["reference_price"] == Decimal("18.45")
    assert rows[0]["recommendation_normalized"] == "BUY"
    assert rows[1]["recommendation_normalized"] == "HOLD"
    assert rows[2]["recommendation_normalized"] == "REVIEW"
    assert rows[2]["target_price"] is None


def test_real_aggregator_fixture_normalizes_institutional_vocabulary():
    html = (FIXTURES / "analysts" / "halkaarz_targets_sample.html").read_text(encoding="utf-8")
    rows = parse_aggregator_recommendations(html)

    assert len(rows) == 4
    assert [row["recommendation_normalized"] for row in rows] == [
        "BUY",
        "BUY",
        "HOLD",
        "SELL",
    ]
    assert rows[0]["ticker"] == "ENJSA"
    assert rows[0]["institution"] == "Tera Yatırım"
    assert rows[0]["target_price"] == Decimal("182.60")


def test_consensus_uses_latest_row_per_institution_and_direct_source_on_tie():
    rows = [
        {
            "ticker": "THYAO",
            "institution": "İş Yatırım",
            "source": "halkaarztakvimi",
            "recommendation_date": date(2026, 8, 1),
            "recommendation_normalized": "HOLD",
            "target_price": Decimal(400),
        },
        {
            "ticker": "THYAO",
            "institution": "İş Yatırım",
            "source": "isyatirim",
            "recommendation_date": date(2026, 8, 1),
            "recommendation_normalized": "BUY",
            "target_price": Decimal(450),
        },
        {
            "ticker": "THYAO",
            "institution": "Deniz Yatırım",
            "source": "halkaarztakvimi",
            "recommendation_date": date(2026, 8, 2),
            "recommendation_normalized": "HOLD",
            "target_price": Decimal(350),
        },
    ]

    result = calculate_consensus(
        rows, market_prices={"THYAO": Decimal(300)}, as_of_date=date(2026, 9, 7)
    )[0]

    assert result["institution_count"] == 2
    assert result["buy_count"] == 1
    assert result["hold_count"] == 1
    assert result["average_target"] == Decimal(400)
    assert result["median_target"] == Decimal(400)
    assert result["recommendation_score"] == Decimal(75)
    assert result["implied_upside_pct"] == Decimal("33.33333333333333333333333330")


def _fund_rows() -> list[dict]:
    fixture = json.loads((FIXTURES / "tefas" / "flow_sample.json").read_text(encoding="utf-8"))
    return map_tefas_snapshots(fixture["info"], fixture["allocation"])


def test_real_tefas_fixture_joins_info_and_allocation():
    rows = _fund_rows()

    assert len(rows) == 4
    aav = next(row for row in rows if row["fund_code"] == "AAV" and row["date"].day == 7)
    assert aav["price"] == Decimal("62.444726")
    assert aav["portfolio_size"] == Decimal("122215944.25")
    assert aav["stock_pct"] == Decimal("89.14")


def test_fund_flow_removes_price_return_effect_and_aggregates_stock_share():
    rows = _fund_rows()
    flows = calculate_fund_flows(rows)
    by_identity = {(row["fund_code"], row["date"]): row for row in rows}
    for flow in flows:
        by_identity[(flow["fund_code"], flow["date"])].update(flow)

    aav = by_identity[("AAV", date(2026, 9, 7))]
    expected = Decimal("122215944.25") - (
        Decimal("121669593.47") * Decimal("62.444726") / Decimal("62.077527")
    )
    assert aav["estimated_net_flow"] == expected
    assert aav["estimated_stock_flow"] == expected * Decimal("89.14") / Decimal(100)

    aggregates = aggregate_fund_flows(rows)
    latest = next(row for row in aggregates if row["date"] == date(2026, 9, 7))
    assert latest["fund_count"] == 2
    assert latest["flow_observation_count"] == 2
    assert latest["total_aum"] == Decimal("2202746082.82")
    assert latest["estimated_stock_flow"] is not None


def test_institutional_routes_validate_enums_without_database_access():
    class EmptyScalars:
        @staticmethod
        def all() -> list:
            return []

    class FakeSession:
        @staticmethod
        async def scalars(statement):
            return EmptyScalars()

    async def override_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        assert client.get("/api/analysts/THYAO/consensus").status_code == 200
        assert client.get("/api/funds/flows?fund_kind=YAT").status_code == 200
        assert client.get("/api/funds/flows?fund_kind=INVALID").status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
