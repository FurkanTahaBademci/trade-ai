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
from app.collectors.institutional_reports import (
    discover_reports,
    max_listing_page,
    parse_listing_date,
    parse_report_fields,
    report_guid,
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
            "recommendation_date": date(2026, 8, 1),
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
    assert result["average_age_days"] == Decimal(37)


def _recommendation(institution: str, when: date, vote: str, target: int) -> dict:
    return {
        "ticker": "THYAO",
        "institution": institution,
        "source": "isyatirim",
        "recommendation_date": when,
        "recommendation_normalized": vote,
        "target_price": Decimal(target),
    }


def test_consensus_drops_recommendations_older_than_max_age():
    rows = [
        _recommendation("A", date(2026, 1, 5), "BUY", 600),
        _recommendation("B", date(2026, 9, 1), "HOLD", 300),
    ]

    result = calculate_consensus(
        rows, market_prices={"THYAO": Decimal(300)}, as_of_date=date(2026, 9, 7)
    )[0]

    assert result["institution_count"] == 1
    assert result["average_target"] == Decimal(300)
    assert result["recommendation_score"] == Decimal(50)


def test_consensus_weights_fresh_recommendations_more():
    rows = [
        _recommendation("Eski", date(2026, 6, 9), "BUY", 500),
        _recommendation("Yeni", date(2026, 9, 7), "SELL", 200),
    ]

    result = calculate_consensus(
        rows, market_prices={"THYAO": Decimal(300)}, as_of_date=date(2026, 9, 7)
    )[0]

    # 90 gunluk yari omur: eski tavsiye yeni tavsiyenin yarisi kadar agirlik alir.
    assert result["average_target"] == Decimal(300)
    assert result["recommendation_score"] == Decimal(100) / 3


def test_consensus_ignores_recommendations_dated_after_as_of():
    rows = [
        _recommendation("A", date(2026, 9, 1), "HOLD", 300),
        _recommendation("B", date(2026, 9, 10), "BUY", 600),
    ]

    result = calculate_consensus(
        rows, market_prices={"THYAO": Decimal(300)}, as_of_date=date(2026, 9, 7)
    )[0]

    assert result["institution_count"] == 1


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


def test_real_phillipcapital_listing_fixture_discovers_reports():
    html = (FIXTURES / "institutional_reports" / "phillipcapital_listing_sample.html").read_text(
        encoding="utf-8"
    )

    entries = discover_reports(html)

    assert len(entries) == 4
    assert entries[0]["title"] == "GRSEL Company Report"
    assert entries[0]["date_text"] == "11 Ağustos 2026"
    assert entries[0]["category"] == "Şirket Raporları"
    assert entries[0]["pdf_url"] == (
        "https://www.phillipcapital.com.tr/Files/CompanyReport/"
        "4a733423-d3b3-4b33-829c-b1d14a22526f.pdf"
    )
    assert max_listing_page(html) == 14


def test_parse_listing_date_reads_turkish_month_names():
    assert parse_listing_date("11 Ağustos 2026") == date(2026, 8, 11)
    assert parse_listing_date("07 Ağustos 2026") == date(2026, 8, 7)


def test_report_guid_extracts_uuid_from_pdf_url():
    url = "https://www.phillipcapital.com.tr/Files/CompanyReport/4a733423-d3b3-4b33-829c-b1d14a22526f.pdf"
    assert report_guid(url) == "4a733423-d3b3-4b33-829c-b1d14a22526f"


def _report_text(name: str) -> str:
    return (FIXTURES / "institutional_reports" / name).read_text(encoding="utf-8")


def test_real_eregl_tr_report_extracts_target_price_and_hold_rating():
    fields = parse_report_fields(
        _report_text("eregl_tr_page1.txt"),
        pdf_url="https://www.phillipcapital.com.tr/Files/CompanyReport/016858f3-f38e-4b42-bcda-aae16f14d5db.pdf",
        title="EREGL Güncelleme Raporu",
        listing_date=date(2026, 8, 7),
    )

    assert fields is not None
    assert fields["ticker"] == "EREGL"
    assert fields["target_price"] == Decimal("58.30")
    assert fields["reference_price"] == Decimal("41.56")
    assert fields["upside_pct"] == Decimal("40.3")
    assert fields["recommendation_normalized"] == "HOLD"
    assert fields["recommendation_date"] == date(2026, 8, 7)
    assert fields["source_key"] == "016858f3-f38e-4b42-bcda-aae16f14d5db"


def test_real_eregl_en_report_normalizes_english_rating_label():
    fields = parse_report_fields(
        _report_text("eregl_en_page1.txt"),
        pdf_url="https://www.phillipcapital.com.tr/Files/CompanyReport/0654e001-8778-4847-a71a-404d3b309822.pdf",
        title="EREGL Company Update Report",
        listing_date=date(2026, 8, 7),
    )

    assert fields is not None
    assert fields["recommendation_raw"] == "Market Perform"
    assert fields["recommendation_normalized"] == "HOLD"
    assert fields["target_price"] == Decimal("58.30")


def test_real_astor_initiation_report_uses_dot_decimals_and_buy_rating():
    fields = parse_report_fields(
        _report_text("astor_tr_page1.txt"),
        pdf_url="https://www.phillipcapital.com.tr/Files/CompanyReport/3f727054-510f-405b-aeae-2bbef9ac5772.pdf",
        title="Şirket Raporu – ASTOR ENERJİ",
        listing_date=date(2024, 1, 16),
    )

    assert fields is not None
    assert fields["ticker"] == "ASTOR"
    assert fields["target_price"] == Decimal("177.80")
    assert fields["reference_price"] == Decimal("103.80")
    assert fields["upside_pct"] == Decimal(71)
    assert fields["recommendation_normalized"] == "BUY"
    assert fields["recommendation_date"] == date(2024, 1, 16)


def test_meeting_note_template_without_target_table_is_skipped():
    fields = parse_report_fields(
        _report_text("kmpur_meeting_note_page1.txt"),
        pdf_url="https://www.phillipcapital.com.tr/Files/CompanyReport/04b0df31-f997-4f38-8778-e6ae77d9760c.pdf",
        title="KMPUR - Toplantı Notu",
        listing_date=date(2026, 3, 13),
    )

    assert fields is None


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


def test_fund_flow_collector_retries_on_connection_error():
    from unittest.mock import MagicMock, patch

    import httpx
    from tenacity import wait_none

    from app.collectors.fund_flows import FundFlowCollector

    session = MagicMock()
    collector = FundFlowCollector(session)
    collector._rate_limit_per_sec = None

    attempts = 0

    async def mock_post(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"resultList": []})
        return resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        collector._post_tefas.retry.wait = wait_none()
        import asyncio
        data = asyncio.run(collector._post_tefas("https://test.tefas.gov.tr", {}))
        assert data == {"resultList": []}
        assert attempts == 3


