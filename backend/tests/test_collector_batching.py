"""Toplu (cok satirli) upsert, tekrar ayiklama ve degismeyen satir korumasi testleri.

Testler DB'ye baglanmaz; collector'larin urettigi ifadeler yakalanip PostgreSQL
diyalektiyle derlenerek incelenir.
"""

import copy
import json
import re
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.dml import Insert

from app.collectors.analysts import AnalystCollector
from app.collectors.base import chunked, dedupe_last, row_changed
from app.collectors.fundamentals import FundamentalsCollector, map_financial_response
from app.collectors.kap import KapCollector
from app.collectors.news import NEWS_FEEDS, NewsCollector
from app.models import AnalystRecommendation, FinancialFact, KapDisclosure, NewsArticle

FIXTURES = Path(__file__).parent / "fixtures"


class _Result:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def all(self):
        return self._rows


class _CaptureSession:
    """SELECT'lere bos/verilen yanit doner, INSERT ifadelerini saklar."""

    def __init__(self, scalars=()):
        self.inserts: list[Insert] = []
        self._scalars = list(scalars)

    async def execute(self, statement):
        if isinstance(statement, Insert):
            self.inserts.append(statement)
        return _Result()

    async def scalars(self, statement):
        return _Result(self._scalars)

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _compiled(statement):
    return statement.compile(dialect=postgresql.dialect())


def _rows(statement, columns):
    """Cok satirli INSERT'in parametrelerinden satirlari geri kurar.

    Varsayilani olmayan kolonlar her satirda `<kolon>_m<i>` adiyla derlenir.
    """
    params = _compiled(statement).params
    count = sum(1 for key in params if re.fullmatch(rf"{columns[0]}_m\d+", key))
    return [{column: params[f"{column}_m{index}"] for column in columns} for index in range(count)]


def _inserts_into(session, model):
    return [stmt for stmt in session.inserts if stmt.table.name == model.__tablename__]


def test_dedupe_last_keeps_last_value_in_first_seen_order():
    rows = [{"k": 1, "v": "a"}, {"k": 2, "v": "b"}, {"k": 1, "v": "c"}]

    assert dedupe_last(rows, lambda row: row["k"]) == [{"k": 1, "v": "c"}, {"k": 2, "v": "b"}]


def test_chunked_keeps_every_row_once():
    assert [list(part) for part in chunked([1, 2, 3, 4, 5], 2)] == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 3)) == []


def test_row_changed_skips_unchanged_rows_and_compares_json_as_jsonb():
    stmt = pg_insert(KapDisclosure).values(disclosure_index=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[KapDisclosure.disclosure_index],
        set_={"summary": stmt.excluded.summary},
        where=row_changed(KapDisclosure, stmt.excluded, ("summary", "raw_list_item")),
    )

    sql = str(_compiled(stmt))

    assert "kap_disclosure.summary IS DISTINCT FROM excluded.summary" in sql
    # json tipinde esitlik operatoru yok; jsonb'ye cevrilmeden kiyaslanamaz.
    assert (
        "CAST(kap_disclosure.raw_list_item AS JSONB) IS DISTINCT FROM "
        "CAST(excluded.raw_list_item AS JSONB)"
    ) in sql


async def test_news_entries_are_written_in_one_guarded_upsert():
    payloads = {
        feed.url: (FIXTURES / "rss" / f"{feed.name}_sample.xml").read_bytes() for feed in NEWS_FEEDS
    }

    class FixtureNewsCollector(NewsCollector):
        async def get_bytes(self, url, **kwargs):
            return payloads[url]

    session = _CaptureSession()
    result = await FixtureNewsCollector(session).run()

    inserts = _inserts_into(session, NewsArticle)
    assert len(inserts) == 1
    assert len(_rows(inserts[0], ["url_hash"])) == result["unique"] > 100
    sql = str(_compiled(inserts[0]))
    assert "ON CONFLICT (url_hash) DO UPDATE" in sql
    assert "news_article.title IS DISTINCT FROM excluded.title" in sql


async def test_kap_skips_malformed_list_row_and_upserts_rest_in_one_statement():
    items = json.loads((FIXTURES / "kap" / "disclosure_list_sample.json").read_text("utf-8"))
    broken = {"disclosureIndex": 999, "kapTitle": "publishDate yok"}
    detail = json.loads((FIXTURES / "kap" / "disclosure_detail_sample.json").read_text("utf-8"))

    class FixtureKapCollector(KapCollector):
        async def _fetch_list(self):
            return [*items, broken]

        async def get_json(self, url, **kwargs):
            return detail

        async def _save_detail(self, disclosure_index, payload):
            return 0

    session = _CaptureSession()
    result = await FixtureKapCollector(session).run()

    assert result["listed"] == result["details_fetched"] == len(items)
    assert [failure["position"] for failure in result["list_failures"]] == [len(items)]
    inserts = _inserts_into(session, KapDisclosure)
    assert len(inserts) == 1
    assert len(_rows(inserts[0], ["disclosure_index"])) == len(items)


async def test_kap_list_row_without_index_is_skipped_not_fatal():
    item = json.loads((FIXTURES / "kap" / "disclosure_list_sample.json").read_text("utf-8"))[0]
    no_index = {key: value for key, value in item.items() if key != "disclosureIndex"}

    class OneDayCollector(KapCollector):
        async def post_json(self, url, json, **kwargs):
            return [no_index, item]

    rows = await OneDayCollector(_CaptureSession(), lookback_days=1)._fetch_list()

    assert rows == [item]


async def test_fundamentals_duplicate_item_is_upserted_once_with_last_value():
    payload = json.loads(
        (FIXTURES / "financials" / "thyao_2025_sample.json").read_text(encoding="utf-8")
    )
    duplicate = copy.deepcopy(payload["value"][0])
    duplicate["value1"] = "123456"
    payload["value"].append(duplicate)
    unique = {
        (row["item_code"], row["period"])
        for row in map_financial_response("THYAO", "XI_29", 2025, payload)
    }

    class FixtureFundamentalsCollector(FundamentalsCollector):
        async def get_json(self, url, **kwargs):
            return payload

    session = _CaptureSession(scalars=["THYAO"])
    result = await FixtureFundamentalsCollector(session, tickers=["THYAO"], years=[2025]).run()

    assert result["failures"] == {}
    assert result["facts"] > len(unique)  # tekrar eden kalem sayaca dahil, yaziya degil
    inserts = _inserts_into(session, FinancialFact)
    assert len(inserts) == 1
    rows = _rows(inserts[0], ["item_code", "period", "value"])
    assert sorted((row["item_code"], row["period"]) for row in rows) == sorted(unique)
    written = next(
        row for row in rows if row["item_code"] == duplicate["itemCode"] and row["period"] == 3
    )
    assert str(written["value"]) == "123456"


async def test_analyst_duplicate_source_key_is_upserted_once(monkeypatch):
    from app.collectors import analysts

    html = {
        analysts.ISYATIRIM_URL: (
            FIXTURES / "analysts" / "isyatirim_tracking_sample.html"
        ).read_bytes(),
        analysts.AGGREGATOR_URL: (
            FIXTURES / "analysts" / "halkaarz_targets_sample.html"
        ).read_bytes(),
    }
    parsed = analysts.parse_isyatirim_recommendations(
        html[analysts.ISYATIRIM_URL].decode()
    ) + analysts.parse_aggregator_recommendations(html[analysts.AGGREGATOR_URL].decode())
    original = analysts.parse_isyatirim_recommendations
    monkeypatch.setattr(
        analysts,
        "parse_isyatirim_recommendations",
        lambda text: [*original(text), dict(original(text)[0])],
    )

    class FixtureAnalystCollector(AnalystCollector):
        async def get_bytes(self, url, **kwargs):
            return html[url]

    session = _CaptureSession(scalars=sorted({row["ticker"] for row in parsed}))
    result = await FixtureAnalystCollector(session).run()

    assert result["accepted"] == len(parsed) + 1
    inserts = _inserts_into(session, AnalystRecommendation)
    assert len(inserts) == 1
    keys = [row["source_key"] for row in _rows(inserts[0], ["source_key"])]
    assert sorted(keys) == sorted({row["source_key"] for row in parsed})
