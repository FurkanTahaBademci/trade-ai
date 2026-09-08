"""Coklu RSS kaynagindan haber toplayicisi (bkz. NEWS_FEEDS).

Idempotency anahtari, takip parametrelerinden arindirilmis URL'nin SHA-256
ozetidir. Ticker eslemesi yalnizca aktif instrument evrenindeki acik kodlari
kullanir; sirket adindan tahmin yapmaz.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectorError
from app.models import Instrument, NewsArticle


@dataclass(frozen=True)
class NewsFeed:
    name: str
    url: str
    naive_timezone: tzinfo = UTC


NEWS_FEEDS = (
    NewsFeed("bloomberght", "https://www.bloomberght.com/rss"),
    # Bu feed offset yazmiyor. Resmi makale sayfasindaki TRT saati RSS'ten
    # uc saat ileride oldugu icin naive deger UTC olarak yorumlanir.
    NewsFeed("investing_tr", "https://tr.investing.com/rss/news.rss"),
    # Asagidaki uc kaynak da pubDate'te acik UTC offset'i tasiyor (+0300/+0000),
    # naive_timezone fallback'i hicbir zaman kullanilmiyor.
    NewsFeed("aa_ekonomi", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi"),
    NewsFeed("dunya", "https://www.dunya.com/rss?sfid=1"),
    NewsFeed("foreks", "https://www.foreks.com/rss"),
)

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
}
_EXPLICIT_TICKER_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,8})(?![A-Za-z0-9])")


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {"br", "div", "li", "p"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in {"div", "li", "p"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def canonicalize_url(value: str) -> str:
    """HTTP(S) URL'ini idempotency icin deterministik hale getir."""
    raw = value.strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise CollectorError(f"Haber URL'i gecersiz: {value!r}")

    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_KEYS
    ]
    query.sort()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def parse_news_datetime(value: str, *, naive_timezone: tzinfo = UTC) -> datetime:
    """RFC 2822 veya ISO tarihini timezone-aware UTC'ye cevir."""
    raw = value.strip()
    if not raw:
        raise CollectorError("Haber yayin tarihi bos")
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise CollectorError(f"Haber tarih formati taninmadi: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=naive_timezone)
    return parsed.astimezone(UTC)


def find_ticker_codes(
    title: str,
    summary: str | None,
    canonical_url: str,
    known_tickers: set[str],
) -> list[str]:
    """Metin ve URL'de acikca gecen, bilinen ticker kodlarini bul."""
    text_candidates = set(_EXPLICIT_TICKER_RE.findall(f"{title} {summary or ''}"))
    # URL slug'larini buyuk harfe cevirip eslemek HEDEF/KENT gibi ayni zamanda
    # kelime olan ticker'larda false-positive uretir. Yalniz URL'de de gercekten
    # buyuk harfle yazilmis kodlari kabul et.
    url_candidates = set(_EXPLICIT_TICKER_RE.findall(urlsplit(canonical_url).path))
    return sorted((text_candidates | url_candidates) & known_tickers)


def _entry_image_url(entry: dict) -> str | None:
    for link in entry.get("links") or []:
        if not isinstance(link, dict):
            continue
        media_type = str(link.get("type") or "").lower()
        if link.get("rel") == "enclosure" and media_type.startswith("image/"):
            href = str(link.get("href") or "").strip()
            return href or None
    return None


def _json_safe_entry(entry: object) -> dict:
    raw = json.loads(json.dumps(dict(entry), ensure_ascii=False, default=str))
    if not isinstance(raw, dict):  # pragma: no cover - feedparser girdisi daima mapping
        raise CollectorError("RSS satiri JSON nesnesine cevrilemedi")
    return raw


def map_news_entry(
    source: str,
    entry: dict,
    known_tickers: set[str],
    *,
    naive_timezone: tzinfo = UTC,
) -> dict:
    """Tek RSS satirini NewsArticle alanlarina ceviren saf fonksiyon."""
    title = html_to_text(str(entry.get("title") or ""))
    link = str(entry.get("link") or "").strip()
    published = entry.get("published") or entry.get("updated")
    if not title or not link or not published:
        raise CollectorError(
            f"RSS satirinda title/link/published eksik: alanlar={sorted(entry.keys())}"
        )

    canonical_url = canonicalize_url(link)
    summary_value = entry.get("summary") or entry.get("description")
    summary = html_to_text(str(summary_value)) if summary_value else None
    author = str(entry.get("author") or "").strip() or None
    return {
        "source": source,
        "source_guid": str(entry.get("id") or entry.get("guid") or "").strip() or None,
        "canonical_url": canonical_url,
        "url_hash": hashlib.sha256(canonical_url.encode()).hexdigest(),
        "title": title,
        "summary": summary,
        "author": author,
        "image_url": _entry_image_url(entry),
        "published_at": parse_news_datetime(str(published), naive_timezone=naive_timezone),
        "ticker_codes": find_ticker_codes(title, summary, canonical_url, known_tickers),
        "raw_entry": _json_safe_entry(entry),
    }


class NewsCollector(BaseCollector):
    name = "news"

    def __init__(
        self,
        session: AsyncSession,
        *,
        sources: tuple[NewsFeed, ...] = NEWS_FEEDS,
    ) -> None:
        super().__init__(rate_limit_per_sec=1.0)
        if not sources:
            raise ValueError("En az bir haber kaynagi gerekli")
        self._session = session
        self._sources = sources

    async def _known_tickers(self) -> set[str]:
        result = await self._session.scalars(
            select(Instrument.ticker).where(Instrument.is_active.is_(True))
        )
        return set(result.all())

    async def run(self) -> dict:
        known_tickers = await self._known_tickers()
        by_hash: dict[str, dict] = {}
        source_failures: dict[str, str] = {}
        entry_failures: list[dict[str, str | int]] = []
        sources_ok = 0
        listed = 0

        for source in self._sources:
            try:
                payload = await self.get_bytes(source.url)
                parsed = feedparser.parse(payload)
                if not parsed.entries:
                    raise CollectorError(
                        f"{source.name} RSS bos"
                        + (f": {parsed.bozo_exception}" if parsed.bozo else "")
                    )
                for position, entry in enumerate(parsed.entries):
                    listed += 1
                    try:
                        mapped = map_news_entry(
                            source.name,
                            entry,
                            known_tickers,
                            naive_timezone=source.naive_timezone,
                        )
                        by_hash[mapped["url_hash"]] = mapped
                    except Exception as exc:  # noqa: BLE001 - tek bozuk satir batch'i durdurmasin
                        entry_failures.append(
                            {"source": source.name, "position": position, "error": str(exc)}
                        )
                        self.log.warning(
                            "news_entry_failed",
                            source=source.name,
                            position=position,
                            error=str(exc),
                        )
                sources_ok += 1
            except Exception as exc:  # noqa: BLE001 - diger RSS kaynaklarini dene
                source_failures[source.name] = str(exc)
                self.log.error("news_source_failed", source=source.name, error=str(exc))

        if sources_ok == 0:
            raise CollectorError(f"Tum haber kaynaklari basarisiz: {source_failures}")

        hashes = list(by_hash)
        existing_hashes: set[str] = set()
        if hashes:
            result = await self._session.scalars(
                select(NewsArticle.url_hash).where(NewsArticle.url_hash.in_(hashes))
            )
            existing_hashes = set(result.all())

        for fields in by_hash.values():
            stmt = pg_insert(NewsArticle).values(**fields)
            stmt = stmt.on_conflict_do_update(
                index_elements=[NewsArticle.url_hash],
                set_={
                    "source": stmt.excluded.source,
                    "source_guid": stmt.excluded.source_guid,
                    "canonical_url": stmt.excluded.canonical_url,
                    "title": stmt.excluded.title,
                    "summary": stmt.excluded.summary,
                    "author": stmt.excluded.author,
                    "image_url": stmt.excluded.image_url,
                    "published_at": stmt.excluded.published_at,
                    "ticker_codes": stmt.excluded.ticker_codes,
                    "raw_entry": stmt.excluded.raw_entry,
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(stmt)
        await self._session.commit()

        return {
            "sources_ok": sources_ok,
            "source_failures": source_failures,
            "listed": listed,
            "unique": len(by_hash),
            "new": len(set(hashes) - existing_hashes),
            "upserted": len(by_hash),
            "entry_failures": entry_failures,
        }
