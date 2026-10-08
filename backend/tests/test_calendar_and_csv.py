"""Takvim siniflandirici, takvim endpoint'i ve CSV kacislama testleri (agsiz)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.routers.calendar import list_calendar_events
from app.api.routers.signals import router as signals_router
from app.core.csv_export import BOM, build_csv, sanitize_cell
from app.main import app
from app.market_calendar.classifier import EventType, classify_disclosure


@pytest.mark.parametrize(
    ("title", "subject", "klass", "expected", "detail"),
    [
        ("Finansal Rapor", None, "FR", EventType.FINANCIAL_REPORT, None),
        ("Özel Durum", "BİLANÇO duyurusu", None, EventType.FINANCIAL_REPORT, None),
        ("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", None, "DG", EventType.DIVIDEND, None),
        ("X", "KÂR PAYI Dağıtımı", None, EventType.DIVIDEND, None),
        ("Genel Kurul İşlemlerine İlişkin Bildirim", None, None, EventType.GENERAL_ASSEMBLY, None),
        ("Sermaye Artırımı - Bedelsiz", None, None, EventType.CAPITAL_INCREASE, "Bedelsiz"),
        ("Bedelli Sermaye Artırımı", None, None, EventType.CAPITAL_INCREASE, "Bedelli"),
        ("Sermaye Artırımı Hakkında", None, None, EventType.CAPITAL_INCREASE, None),
    ],
)
def test_classifier_maps_kap_titles(title, subject, klass, expected, detail):
    result = classify_disclosure(title=title, subject=subject, disclosure_class=klass)
    assert result is not None
    assert result.event_type == expected
    assert result.detail == detail


def test_classifier_ignores_unrelated_disclosures():
    assert classify_disclosure(title="Sözleşme İmzalanması", subject="Özel Durum") is None
    assert classify_disclosure(title=None, subject=None) is None


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1)", "-2+3", "@cmd", "\t=x", "  =x"])
def test_sanitize_neutralizes_formula_prefixes(value):
    assert sanitize_cell(value).startswith("'")


def test_sanitize_keeps_safe_text():
    assert sanitize_cell("THYAO") == "THYAO"
    assert sanitize_cell("a=b") == "a=b"


def test_build_csv_bom_delimiter_and_escaping():
    raw = build_csv(
        ["Hisse", "Not"],
        [("THYAO", '=HYPERLINK("x";"y")'), ("A;B", -1.5), ("C", Decimal("2.50")), ("D", None)],
    )
    text = raw.decode("utf-8")
    assert text.startswith(BOM)
    lines = text.lstrip(BOM).split("\r\n")
    assert lines[0] == "Hisse;Not"
    assert lines[1] == 'THYAO;"\'=HYPERLINK(""x"";""y"")"'
    assert lines[2] == '"A;B";-1,5'  # sayilar formul sayilmaz, ondalik virgul
    assert lines[3] == "C;2,50"
    assert lines[4] == "D;"


def test_routes_registered_and_csv_before_ticker_catchall():
    paths = list(app.openapi()["paths"])
    assert "/api/calendar" in paths
    assert "/api/signals/export.csv" in paths
    assert "/api/paper/portfolios/{portfolio_id}/trades.csv" in paths
    routes = [r.path for r in signals_router.routes]
    assert routes.index("/api/signals/export.csv") < routes.index("/api/signals/{ticker}")


async def test_calendar_endpoint_merges_ppk_and_kap_events():
    decision = SimpleNamespace(
        decision_no="PPK-2026-10",
        decision_date=date(2099, 10, 22),
        status="SCHEDULED",
        title="PPK toplantısı",
        policy_rate=Decimal("40.000"),
    )
    kap_rows = [
        SimpleNamespace(
            disclosure_index=7,
            published_at=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
            kap_title="Kar Payı Dağıtım İşlemlerine İlişkin Bildirim",
            subject=None,
            disclosure_class="DG",
            ticker_codes=["THYAO"],
        ),
        SimpleNamespace(
            disclosure_index=8,
            published_at=datetime(2026, 10, 6, 9, 0, tzinfo=UTC),
            kap_title="Sözleşme İmzalanması",
            subject=None,
            disclosure_class="ODA",
            ticker_codes=["ASELS"],
        ),
    ]
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [decision]
    db.scalars.return_value = scalars
    result = MagicMock()
    result.scalars.return_value.unique.return_value.all.return_value = kap_rows
    db.execute.return_value = result

    events = await list_calendar_events(
        db=db, start=date(2099, 10, 1), end=date(2099, 12, 31), types=None, ticker=None
    )
    assert [e.id for e in events] == ["kap-7", "ppk-PPK-2026-10"]
    assert events[0].tickers == ["THYAO"]
    assert events[1].upcoming is True


async def test_calendar_type_filter_skips_ppk_query():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.unique.return_value.all.return_value = []
    db.execute.return_value = result
    events = await list_calendar_events(
        db=db,
        start=date(2026, 10, 1),
        end=date(2026, 10, 31),
        types=[EventType.DIVIDEND],
        ticker="thyao",
    )
    assert events == []
    db.scalars.assert_not_called()
