"""KAP metin temizligi ve KAP test bildirimi filtresi testleri (gercek fixture'lar)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.routers.kap import get_disclosure, list_disclosures
from app.collectors.kap import map_disclosure_detail, map_disclosure_list_item
from app.collectors.kap_content import (
    clean_kap_body_text,
    is_kap_test_disclosure,
    kap_test_disclosure_clause,
    not_kap_test_disclosure,
)
from app.models import KapDisclosure
from tests.test_kap_collector_idempotency import _FixtureKapCollector, _MemorySession

FIXTURES = Path(__file__).parent / "fixtures" / "kap"

# 1683386 bildiriminin onceki surumde DB'ye yazilan body_text'i (canli gozlem).
LEGACY_TEST_NOTIFICATION_TEXT = """İlgili Şirketler
İlgili Fonlar
[]
Türkçe
oda_NotificationAboutSuspensionofBISTStocks|
Devre Kesici Uygulaması
oda_AnnouncementContentSection|
Bildirim İçeriği
oda_EmptyField|
oda_ExplanationSection|
Açıklamalar
oda_ExplanationTextBlock|
Test bildirimidir, dikkate almayiniz. Zaman=20261017-025352."""


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _assert_no_template_noise(text: str) -> None:
    lines = text.splitlines()
    assert not [line for line in lines if line.startswith("oda_") or line.endswith("|")]
    assert "[]" not in lines
    assert "Türkçe" not in lines


def test_detail_text_has_no_template_keys_at_ingest():
    body = map_disclosure_detail(_load("disclosure_detail_sample.json"))["body_text"]

    _assert_no_template_noise(body)
    assert body.splitlines()[:4] == [
        "Özel Durum Açıklaması (Genel)",
        "Yapılan Açıklama Güncelleme mi?",
        "Hayır",
        "Yapılan Açıklama Düzeltme mi?",
    ]
    assert "Bankamız, Uluslararası İmar ve Kalkınma Bankası" in body
    assert "İlgili Şirketler" not in body


def test_legacy_stored_text_is_cleaned_at_read_time():
    assert clean_kap_body_text(LEGACY_TEST_NOTIFICATION_TEXT) == (
        "Devre Kesici Uygulaması\n"
        "Bildirim İçeriği\n"
        "Açıklamalar\n"
        "Test bildirimidir, dikkate almayiniz. Zaman=20261017-025352."
    )
    # Ingest yolu ayni sonucu uretir: temizlik iki kez uygulanabilir (idempotent).
    ingested = map_disclosure_detail(_load("detail_test_notification.json"))["body_text"]
    assert ingested == clean_kap_body_text(LEGACY_TEST_NOTIFICATION_TEXT)
    assert clean_kap_body_text(ingested) == ingested


def test_cleaning_keeps_real_content_and_values():
    for name in ("detail_dividend.json", "detail_general_assembly.json"):
        body = map_disclosure_detail(_load(name))["body_text"]
        assert clean_kap_body_text(body) == body
    text = "Dil\nTürkçe\nİlgili Şirketler\n[GUBRF]\nEvet (Yes)"
    assert clean_kap_body_text(text) == "Dil\nTürkçe\nİlgili Şirketler\n[GUBRF]\nEvet"
    assert clean_kap_body_text(None) is None
    assert clean_kap_body_text("oda_EmptyField|\n[]") is None


def test_kap_test_notifications_are_recognised_from_list_metadata():
    rows = [map_disclosure_list_item(item) for item in _load("list_with_test_notifications.json")]
    flags = {
        row["disclosure_index"]: is_kap_test_disclosure(
            ticker_codes=row["ticker_codes"],
            kap_title=row["kap_title"],
            subject=row["subject"],
            summary=row["summary"],
        )
        for row in rows
    }
    # 1683385: KTEST / "KAP TEST A.Ş.", 1683386: ozet "Test bildirimi",
    # 1683384: gercek SPK tedbir karari.
    assert flags == {1683386: True, 1683385: True, 1683384: False}


def test_real_disclosures_are_not_flagged_as_test():
    for item in _load("disclosure_list_sample.json"):
        row = map_disclosure_list_item(item)
        assert not is_kap_test_disclosure(
            ticker_codes=row["ticker_codes"],
            kap_title=row["kap_title"],
            subject=row["subject"],
            summary=row["summary"],
        )
    assert not is_kap_test_disclosure(subject="Test sürecine ilişkin açıklama")
    assert not is_kap_test_disclosure(summary="Yazılım test bildirimi hakkında bilgilendirme")
    assert not is_kap_test_disclosure(body_text="Ürünlerimizin test süreçleri tamamlandı.")


def test_test_notification_body_phrase_is_recognised():
    body = map_disclosure_detail(_load("detail_test_notification.json"))["body_text"]
    assert is_kap_test_disclosure(subject="Pay Bazında Devre Kesici Bildirimi", body_text=body)
    assert is_kap_test_disclosure(body_text="TEST BİLDİRİMİDİR, DİKKATE ALMAYINIZ.")


def test_sql_clause_compiles_for_postgres():
    dialect = postgresql.dialect()
    metadata_only = str(kap_test_disclosure_clause().compile(dialect=dialect))
    with_body = str(not_kap_test_disclosure(include_body=True).compile(dialect=dialect))

    assert "body_text" not in metadata_only
    assert "ticker_codes" in metadata_only
    assert "body_text" in with_body
    assert with_body.startswith("NOT coalesce(")


async def test_sql_filter_excludes_test_rows_and_keeps_nulls():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    published = datetime(2026, 10, 17, tzinfo=UTC)

    def row(index, *, title="GERCEK A.S.", subject=None, summary=None, tickers=(), body=None):
        return KapDisclosure(
            disclosure_index=index,
            published_at=published,
            kap_title=title,
            subject=subject,
            summary=summary,
            ticker_codes=list(tickers),
            body_text=body,
            raw_list_item={},
        )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(KapDisclosure.__table__.create)
        async with AsyncSession(engine) as db:
            db.add_all(
                [
                    row(1, title="KAP TEST A.Ş.", subject="Test Bildirimi", tickers=["KTEST"]),
                    row(2, subject="Pay Bazında Devre Kesici Bildirimi", summary="Test bildirimi"),
                    row(3, body="Test bildirimidir, dikkate almayiniz. Zaman=1"),
                    row(4),  # subject/summary/body NULL: NOT(NULL) satiri dusurmemeli
                    row(5, subject="Test sürecine ilişkin açıklama", tickers=["KTESTX"]),
                ]
            )
            await db.commit()

            async def visible(include_body):
                stmt = select(KapDisclosure.disclosure_index).where(
                    not_kap_test_disclosure(include_body=include_body)
                )
                return sorted((await db.scalars(stmt)).all())

            assert await visible(False) == [3, 4, 5]
            assert await visible(True) == [4, 5]
    finally:
        await engine.dispose()


async def test_collector_skips_test_notifications():
    list_items = _load("list_with_test_notifications.json")
    detail = _load("disclosure_detail_sample.json")
    session = _MemorySession()
    collector = _FixtureKapCollector(session, list_items, detail)

    first = await collector.run()
    second = await collector.run()

    assert first["listed"] == 1
    assert first["test_skipped"] == 2
    assert first["new"] == 1
    assert set(session.details) == {1683384}
    assert second["new"] == 0
    assert second["details_fetched"] == 0
    assert collector.detail_request_count == 1


def _stored(index: int, **fields) -> KapDisclosure:
    values = {
        "disclosure_index": index,
        "published_at": datetime(2026, 10, 17, tzinfo=UTC),
        "kap_title": "GERCEK A.S.",
        "subject": "Özel Durum Açıklaması (Genel)",
        "summary": None,
        "disclosure_class": "ODA",
        "disclosure_type": "ODA",
        "disclosure_category": "ODA",
        "ticker_codes": ["GUBRF"],
        "is_late": False,
        "attachment_count": 0,
        "body_html": None,
        "body_text": None,
        "raw_list_item": {},
        "attachments": [],
        **fields,
    }
    return KapDisclosure(**values)


async def test_detail_api_cleans_legacy_text_and_hides_test_notifications():
    legacy = "Türkçe\noda_ExplanationTextBlock|\nŞirketimiz yeni yatırım kararı aldı."
    db = AsyncMock()
    db.get.return_value = _stored(10, body_text=legacy)

    out = await get_disclosure(disclosure_index=10, db=db)

    assert out.body_text == "Şirketimiz yeni yatırım kararı aldı."
    assert db.get.return_value.body_text == legacy  # ORM nesnesi (DB) degismez

    db.get.return_value = _stored(
        1683386,
        subject="Pay Bazında Devre Kesici Bildirimi",
        body_text=LEGACY_TEST_NOTIFICATION_TEXT,
    )
    with pytest.raises(HTTPException) as excinfo:
        await get_disclosure(disclosure_index=1683386, db=db)
    assert excinfo.value.status_code == 404


async def test_list_api_excludes_test_notifications_without_reading_body():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.unique.return_value.all.return_value = []
    db.execute.return_value = result

    await list_disclosures(
        db=db, ticker=None, disclosure_class=None, before=None, before_index=None, limit=5
    )

    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "NOT coalesce(" in sql
    assert "kap_disclosure.ticker_codes AS VARCHAR) LIKE" in sql
    assert "body_text LIKE" not in sql.split("FROM", 1)[1]
