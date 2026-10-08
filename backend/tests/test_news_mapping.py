"""Haber RSS donusumu, URL kimligi ve ticker esleme testleri."""

from datetime import UTC, datetime
from pathlib import Path

import feedparser
import pytest

from app.collectors.base import CollectorError
from app.collectors.news import NEWS_FEEDS, canonicalize_url, map_news_entry, parse_news_datetime

FIXTURES = Path(__file__).parent / "fixtures" / "rss"


def test_bloomberght_uses_the_current_direct_rss_endpoint():
    bloomberg = next(feed for feed in NEWS_FEEDS if feed.name == "bloomberght")

    assert bloomberg.url == "https://www.bloomberght.com/rss/tum-haberler.xml"


def test_bloomberght_fixture_maps_all_entries_with_aware_utc_dates():
    parsed = feedparser.parse((FIXTURES / "bloomberght_sample.xml").read_bytes())

    rows = [map_news_entry("bloomberght", entry, set()) for entry in parsed.entries]

    assert len(rows) == 20
    assert rows[0]["published_at"] == datetime(2026, 8, 25, 20, 4, 47, tzinfo=UTC)
    assert rows[0]["canonical_url"].startswith("https://www.bloomberght.com/")
    assert len(rows[0]["url_hash"]) == 64


def test_investing_fixture_extracts_image_author_and_explicit_ticker():
    parsed = feedparser.parse((FIXTURES / "investing_tr_sample.xml").read_bytes())

    rows = [map_news_entry("investing_tr", entry, {"TMPOL"}) for entry in parsed.entries]

    assert len(rows) == 10
    assert rows[0]["published_at"] == datetime(2026, 9, 5, 21, 6, 23, tzinfo=UTC)
    assert rows[0]["author"] == "Investing.com"
    assert rows[0]["image_url"].endswith(".jpg")
    assert rows[-1]["ticker_codes"] == ["TMPOL"]


def test_aa_ekonomi_fixture_maps_all_entries_with_explicit_offset():
    parsed = feedparser.parse((FIXTURES / "aa_ekonomi_sample.xml").read_bytes())

    rows = [map_news_entry("aa_ekonomi", entry, set()) for entry in parsed.entries]

    assert len(rows) == 30
    assert rows[0]["published_at"] == datetime(2026, 9, 7, 20, 54, 26, tzinfo=UTC)
    assert rows[0]["canonical_url"].startswith("https://www.aa.com.tr/")


def test_dunya_fixture_maps_all_entries_with_explicit_offset():
    parsed = feedparser.parse((FIXTURES / "dunya_sample.xml").read_bytes())

    rows = [map_news_entry("dunya", entry, set()) for entry in parsed.entries]

    assert len(rows) == 25
    assert rows[0]["published_at"] == datetime(2026, 9, 8, 5, 27, 0, tzinfo=UTC)
    assert rows[0]["canonical_url"].startswith("https://www.dunya.com/")


def test_foreks_fixture_maps_all_entries_and_keeps_author():
    parsed = feedparser.parse((FIXTURES / "foreks_sample.xml").read_bytes())

    rows = [map_news_entry("foreks", entry, set()) for entry in parsed.entries]

    assert len(rows) == 15
    assert rows[0]["published_at"] == datetime(2026, 9, 8, 5, 31, 1, tzinfo=UTC)
    assert rows[0]["author"] == "ForInvest"
    assert rows[0]["canonical_url"].startswith("https://www.foreks.com/")


def test_trthaber_fixture_maps_all_entries_with_explicit_offset():
    parsed = feedparser.parse((FIXTURES / "trthaber_sample.xml").read_bytes())

    rows = [map_news_entry("trthaber", entry, set()) for entry in parsed.entries]

    assert len(rows) == 15
    assert rows[0]["published_at"] == datetime(2026, 9, 8, 6, 54, 0, tzinfo=UTC)
    assert rows[0]["canonical_url"].startswith("https://www.trthaber.com/")


def test_canonical_url_removes_tracking_fragment_and_sorts_query():
    first = canonicalize_url(
        "HTTPS://Example.COM:443/path/?z=2&utm_source=rss&a=1&fbclid=abc#section"
    )
    second = canonicalize_url("https://example.com/path?a=1&z=2")

    assert first == "https://example.com/path?a=1&z=2"
    assert first == second


def test_ticker_matching_does_not_infer_lowercase_prose():
    row = map_news_entry(
        "test",
        {
            "title": "Hedef büyüdü ama kod açıkça yazılmadı",
            "link": "https://example.com/hedef-buyudu",
            "published": "Sun, 06 Sep 2026 12:00:00 +0000",
        },
        {"HEDEF"},
    )

    assert row["ticker_codes"] == []


def test_naive_and_offset_dates_normalize_to_utc():
    assert parse_news_datetime("2026-09-05 21:06:23") == datetime(
        2026, 9, 5, 21, 6, 23, tzinfo=UTC
    )
    assert parse_news_datetime("Sun, 06 Sep 2026 03:00:00 +0300") == datetime(
        2026, 9, 6, 0, 0, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "entry",
    [
        {"link": "https://example.com/x", "published": "2026-09-05 00:00:00"},
        {"title": "Baslik", "published": "2026-09-05 00:00:00"},
        {"title": "Baslik", "link": "https://example.com/x"},
    ],
)
def test_required_rss_fields_are_validated(entry):
    with pytest.raises(CollectorError):
        map_news_entry("test", entry, set())
