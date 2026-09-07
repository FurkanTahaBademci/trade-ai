"""KAP collector'in ikinci calismada detaylari yeniden cekmedigi testi."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.collectors.base import CollectorError
from app.collectors.kap import KAP_RESULT_LIMIT, KapCollector, normalize_detail_response

FIXTURES = Path(__file__).parent / "fixtures" / "kap"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def mappings(self):
        return self._rows


class _MemorySession:
    """Bu test icin gereken en kucuk AsyncSession davranisi."""

    def __init__(self, member_oids: list[str] | None = None):
        self.details: dict[int, dict] = {}
        self._member_oids = member_oids or []

    async def execute(self, statement):
        if getattr(statement, "is_select", False):
            names = [description["name"] for description in statement.column_descriptions]
            if names == ["disclosure_index", "raw_detail"]:
                return _Result(list(self.details.items()))
            return _Result([])
        return _Result([])

    async def scalars(self, statement):
        return _Result(self._member_oids)

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _FixtureKapCollector(KapCollector):
    def __init__(self, session, list_items, detail):
        super().__init__(session, download_attachments=False)
        self._list_items = list_items
        self._detail = detail
        self.detail_request_count = 0

    async def _fetch_list(self):
        return self._list_items

    async def get_json(self, url, **kwargs):
        self.detail_request_count += 1
        return self._detail

    async def _save_detail(self, disclosure_index, payload):
        self._session.details[disclosure_index] = normalize_detail_response(payload)
        return 0, 0


class _ListWindowCollector(KapCollector):
    def __init__(self, session, item):
        super().__init__(
            session,
            lookback_days=3,
            end_date=date(2026, 9, 6),
            download_attachments=False,
        )
        self._item = item
        self.payloads = []

    async def post_json(self, url, json, **kwargs):
        self.payloads.append(json)
        return [self._item]


async def test_second_run_creates_no_new_rows_or_detail_requests():
    list_items = json.loads((FIXTURES / "disclosure_list_sample.json").read_text(encoding="utf-8"))[
        :1
    ]
    detail = json.loads((FIXTURES / "disclosure_detail_sample.json").read_text(encoding="utf-8"))
    session = _MemorySession()
    collector = _FixtureKapCollector(session, list_items, detail)

    first = await collector.run()
    second = await collector.run()

    assert first["new"] == 1
    assert first["details_fetched"] == 1
    assert second["new"] == 0
    assert second["details_fetched"] == 0
    assert collector.detail_request_count == 1


class _DailyLimitCollector(KapCollector):
    """Tek istekte KAP gunluk limitine carpan, uye bazli bolmeyi test eder."""

    def __init__(self, session, item):
        super().__init__(
            session,
            lookback_days=1,
            end_date=date(2026, 9, 6),
            download_attachments=False,
        )
        self._item = item
        self.payloads: list[dict] = []

    async def post_json(self, url, json, **kwargs):
        self.payloads.append(json)
        if not json["mkkMemberOidList"]:
            return [self._item] * KAP_RESULT_LIMIT
        return [self._item]


async def test_daily_limit_triggers_member_based_split():
    item = json.loads((FIXTURES / "disclosure_list_sample.json").read_text(encoding="utf-8"))[0]
    session = _MemorySession(member_oids=["OID-1", "OID-2", "OID-3"])
    collector = _DailyLimitCollector(session, item)

    rows = await collector._fetch_list()

    assert len(rows) == 1
    assert len(collector.payloads) == 2
    assert collector.payloads[0]["mkkMemberOidList"] == []
    assert collector.payloads[1]["mkkMemberOidList"] == ["OID-1", "OID-2", "OID-3"]


async def test_daily_limit_without_active_members_raises():
    item = json.loads((FIXTURES / "disclosure_list_sample.json").read_text(encoding="utf-8"))[0]
    collector = _DailyLimitCollector(_MemorySession(member_oids=[]), item)

    with pytest.raises(CollectorError, match="veri kaybi riski var"):
        await collector._fetch_list()


async def test_list_window_is_split_per_day_and_deduplicated():
    item = json.loads((FIXTURES / "disclosure_list_sample.json").read_text(encoding="utf-8"))[0]
    collector = _ListWindowCollector(_MemorySession(), item)

    rows = await collector._fetch_list()

    assert len(rows) == 1
    assert [(p["fromDate"], p["toDate"]) for p in collector.payloads] == [
        ("2026-09-04", "2026-09-04"),
        ("2026-09-05", "2026-09-05"),
        ("2026-09-06", "2026-09-06"),
    ]
