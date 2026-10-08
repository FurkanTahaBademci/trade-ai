"""isyatirimhisse.fetch_index_data satiri -> index_daily alan esleme testleri.

Kolon adlari (INDEX, DATE, VALUE) gercek `fetch_index_data` cagrisindan
dogrulandi.
"""

import json
import math
from datetime import date
from pathlib import Path

from app.collectors.index_prices import map_index_record
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "index"


def test_index_prices_route_is_registered():
    assert "/api/index/{code}/prices" in app.openapi()["paths"]


def _real_shaped_record(**overrides) -> dict:
    base = {"INDEX": "XU100", "DATE": date(2026, 9, 8), "VALUE": 14135.18}
    base.update(overrides)
    return base


def test_maps_real_shaped_record_correctly():
    mapped = map_index_record(_real_shaped_record())

    assert mapped == {"index_code": "XU100", "date": date(2026, 9, 8), "value": 14135.18}


def test_nan_value_is_rejected():
    assert map_index_record(_real_shaped_record(VALUE=math.nan)) is None


def test_missing_index_code_is_rejected():
    assert map_index_record(_real_shaped_record(INDEX=None)) is None


def test_missing_date_is_rejected():
    assert map_index_record(_real_shaped_record(DATE=None)) is None


def test_fixture_maps_all_rows():
    records = json.loads((FIXTURES / "xu100_sample.json").read_text(encoding="utf-8"))
    for record in records:
        record["DATE"] = date.fromisoformat(record["DATE"])

    rows = [mapped for record in records if (mapped := map_index_record(record)) is not None]

    assert len(rows) == 5
    assert rows[0] == {"index_code": "XU100", "date": date(2026, 9, 2), "value": 14050.55957}
    assert rows[-1]["date"] == date(2026, 9, 8)
