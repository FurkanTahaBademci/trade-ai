"""EVDS makro seri ayristirma testleri (sentetik ornek; bkz. collectors/evds.py)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.collectors.base import CollectorError
from app.collectors.evds import (
    EVDS_SERIES,
    build_series_url,
    map_series_response,
    parse_evds_date,
)

FIXTURE = Path(__file__).parent / "fixtures" / "evds" / "series_sample.json"


def test_url_uses_path_style_parameters_with_dash_joined_codes():
    url = build_series_url(["TP.DK.USD.A.YTL", "TP.FG.J0"], date(2026, 9, 1), date(2026, 10, 10))
    assert url == (
        "https://evds2.tcmb.gov.tr/service/evds/series=TP.DK.USD.A.YTL-TP.FG.J0"
        "&startDate=01-09-2026&endDate=10-10-2026&type=json"
    )


def test_daily_and_monthly_dates_are_parsed():
    assert parse_evds_date("02-09-2026") == date(2026, 9, 2)
    assert parse_evds_date("2026-9") == date(2026, 9, 1)
    assert parse_evds_date("") is None


def test_mapping_skips_empty_cells_and_keeps_each_series():
    rows = map_series_response(
        json.loads(FIXTURE.read_text(encoding="utf-8")), list(EVDS_SERIES)
    )
    by_series = {}
    for row in rows:
        by_series.setdefault(row["series_code"], []).append(row)
    assert len(by_series["TP.DK.USD.A.YTL"]) == 2
    assert len(by_series["TP.DK.EUR.A.YTL"]) == 1
    assert by_series["TP.FG.J0"][-1] == {
        "series_code": "TP.FG.J0",
        "date": date(2026, 9, 1),
        "value": Decimal("4290.13"),
    }


def test_invalid_payload_raises():
    with pytest.raises(CollectorError):
        map_series_response({"error": "x"}, list(EVDS_SERIES))


def test_series_summary_computes_change_and_yoy():
    from app.api.routers.macro import summarize_series

    summary = summarize_series(
        "TP.FG.J0",
        [(date(2025, 9, 1), 3300.0), (date(2026, 8, 1), 4200.0), (date(2026, 9, 1), 4290.0)],
    )
    assert summary.latest_date == date(2026, 9, 1)
    assert round(summary.change_pct, 2) == 2.14
    assert round(summary.yoy_pct, 1) == 30.0


def test_daily_series_has_no_yoy():
    from app.api.routers.macro import summarize_series

    summary = summarize_series(
        "TP.DK.USD.A.YTL", [(date(2025, 9, 2), 33.0), (date(2026, 9, 1), 41.0), (date(2026, 9, 2), 41.3)]
    )
    assert summary.yoy_pct is None
