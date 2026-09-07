"""Finansal tablo mapping ve deterministik oran testleri."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.collectors.base import CollectorError
from app.collectors.fundamentals import build_snapshots, map_financial_response
from app.core.db import get_db
from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "financials" / "thyao_2025_sample.json"


def _facts() -> list[dict]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = {**fixture["response_metadata"], "value": fixture["value"]}
    return map_financial_response("THYAO", "XI_29", 2025, payload)


def test_real_fixture_maps_every_non_null_period_value():
    facts = _facts()

    assert len(facts) == 14 * 4
    assert len(
        {
            (row["ticker"], row["financial_group"], row["year"], row["period"], row["item_code"])
            for row in facts
        }
    ) == len(facts)
    cash_q4 = next(row for row in facts if row["item_code"] == "1AA" and row["period"] == 12)
    assert cash_q4["value"] == Decimal(101313500671)
    assert cash_q4["item_name_tr"] == "Nakit ve Nakit Benzerleri"


def test_snapshot_calculates_ratios_yoy_and_score_from_item_codes():
    current = _facts()
    previous = []
    for row in current:
        old = dict(row)
        old["year"] = 2024
        if old["item_code"] == "3C":
            old["value"] = Decimal(1000000000000)
        elif old["item_code"] == "3Z":
            old["value"] = Decimal(100000000000)
        previous.append(old)

    snapshots = build_snapshots([*previous, *current])
    snapshot = next(row for row in snapshots if row["year"] == 2025 and row["period"] == 12)

    assert snapshot["revenue"] == Decimal(1125149219659)
    assert snapshot["ebitda_proxy"] == Decimal(186313920331)
    assert snapshot["revenue_yoy"] == Decimal("0.125149219659")
    assert snapshot["net_income_yoy"] == Decimal("0.39199933601")
    assert snapshot["gross_margin"] == Decimal(183185077752) / Decimal(1125149219659)
    assert snapshot["current_ratio"] == Decimal(513912099203) / Decimal(520581939010)
    assert snapshot["data_completeness"] == 11
    assert Decimal(0) <= snapshot["fundamental_score"] <= Decimal(100)
    assert set(snapshot["score_components"]) == {
        "growth",
        "profitability",
        "balance_sheet",
        "cash_flow",
    }


def test_negative_to_positive_profit_is_treated_as_turnaround():
    facts = [
        {
            "ticker": "TEST",
            "financial_group": "XI_29",
            "exchange": "TRY",
            "year": 2024,
            "period": 12,
            "item_code": "3Z",
            "value": Decimal(-100),
        },
        {
            "ticker": "TEST",
            "financial_group": "XI_29",
            "exchange": "TRY",
            "year": 2025,
            "period": 12,
            "item_code": "3Z",
            "value": Decimal(20),
        },
    ]

    snapshot = next(row for row in build_snapshots(facts) if row["year"] == 2025)

    assert snapshot["net_income_yoy"] == Decimal(1)
    assert snapshot["fundamental_score"] is None


@pytest.mark.parametrize(
    "payload",
    [{}, {"value": {}}, {"ok": False, "value": [], "errorCode": "x"}],
)
def test_invalid_financial_response_is_rejected(payload):
    with pytest.raises(CollectorError):
        map_financial_response("THYAO", "XI_29", 2025, payload)


def test_period_query_accepts_financial_periods_and_rejects_other_values():
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
        assert client.get("/api/fundamentals/THYAO?period=6").status_code == 200
        assert client.get("/api/fundamentals/THYAO?period=4").status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
