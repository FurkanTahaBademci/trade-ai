"""KAP form metninden olay tarihi cikarimi (gercek yanit fixture'lari)."""

import json
from datetime import date
from pathlib import Path

from app.collectors.kap import map_disclosure_detail
from app.market_calendar.classifier import EventType
from app.market_calendar.event_dates import extract_event_date

FIXTURES = Path(__file__).parent / "fixtures" / "kap"


def _body(name: str) -> str:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return map_disclosure_detail(payload)["body_text"]


def test_general_assembly_uses_meeting_date_not_publish_date():
    result = extract_event_date(
        EventType.GENERAL_ASSEMBLY, _body("detail_general_assembly.json")
    )
    assert result is not None
    assert result.event_date == date(2026, 10, 27)


def test_dividend_uses_ex_date_and_reports_payment_date():
    result = extract_event_date(EventType.DIVIDEND, _body("detail_dividend.json"))
    assert result is not None
    assert result.event_date == date(2026, 10, 14)
    assert result.detail == "Hak kullanım 14.10.2026 · ödeme 16.10.2026"


def test_dividend_form_meeting_reference_is_not_a_general_assembly_date():
    # Kar payi formundaki "Konunun Gundemde Yer Aldigi Genel Kurul Tarihi" eslesmemeli.
    assert extract_event_date(EventType.GENERAL_ASSEMBLY, _body("detail_dividend.json")) is None


def test_four_date_row_prefers_finalized_ex_date():
    body = "Kar Payı Ödeme Tarihleri\nPeşin\n01.11.2026\n03.11.2026\n05.11.2026\n04.11.2026"
    result = extract_event_date(EventType.DIVIDEND, body)
    assert result is not None and result.event_date == date(2026, 11, 3)


def test_missing_or_unsupported_inputs_return_none():
    assert extract_event_date(EventType.DIVIDEND, None) is None
    assert extract_event_date(EventType.FINANCIAL_REPORT, "Genel Kurul Tarihi\n01.01.2026") is None
    assert extract_event_date(EventType.DIVIDEND, "Kar Payı Ödeme Tarihleri\nPeşin") is None
