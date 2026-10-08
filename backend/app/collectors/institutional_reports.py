"""PhillipCapital Turkiye'nin ozgun sirket raporu PDF'lerini toplar.

CLAUDE.md'deki "uc kaynak paralel" karari geregi analist sinyali icin
ucuncu (dogrudan kurumsal PDF) bacak. Diger arac kurumlarin (Is Yatirim,
Ak Yatirim, Oyak, QNB Finansinvest, ...) rapor arsivleri ya uyelik
duvarinin arkasinda ya da JS ile render ediliyor; PhillipCapital'in
`arastirma-urunleri` sayfasi login gerektirmeyen, sunucu tarafinda render
edilen (JS gerektirmeyen) tek kaynak olarak dogrulandi (bu oturumda
gercek HTTP istekleriyle).

Rapor PDF'leri sablon acisindan tutarli degil: sadece "Bloomberg Ticker"
satiri iceren (nispeten yeni) sablon guvenilir sekilde ayristirilabiliyor.
"Toplanti Notu" / eski "Company Report" kapak sablonlari yapisal
hedef fiyat tablosu tasimiyor — bu durumda satir sessizce atlanir (isim
eslemesiyle tahmin YAPILMAZ, proje kurali geregi eslesme sadece kod
uzerinden olur).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.analysts import normalize_recommendation, recompute_analyst_consensus
from app.collectors.base import BaseCollector, CollectorError
from app.core.redis import get_redis
from app.models import AnalystRecommendation, Instrument

LISTING_URL = "https://www.phillipcapital.com.tr/arastirma-urunleri"
PDF_BASE_URL = "https://www.phillipcapital.com.tr"
CATEGORY = "Şirket Raporları"
SOURCE_NAME = "phillipcapital_pdf"
INSTITUTION_NAME = "PhillipCapital Yatırım"
# Redis SET: "Bloomberg Ticker" tasimayan/aktif olmayan tickera duşen
# raporlarin GUID'leri — bunlar hicbir zaman DB'ye yazilmadigi icin bu
# cache olmadan her koşuda tekrar indirilip ayristirilirlardi.
_SKIP_CACHE_KEY = "institutional_reports:skipped_guids"

_GUID_RE = re.compile(r"/CompanyReport/([0-9a-fA-F-]{36})\.pdf")
_TICKER_RE = re.compile(r"Bloomberg Ticker[ \t]{2,}([A-Z0-9]{2,6})\s+TI\b")
_HEADER_DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
_PAGE_LINK_RE = re.compile(r"[?&]page=(\d+)")

# Sablonlar arasi Turkce/Ingilizce etiket varyantlari; ozel/uzun etiketler
# once denenir (aksi halde "Hedef Fiyat" gibi genel etiket, "Hisse Basina
# Hedef Fiyat, TL" satirinin bir parcasini yanlislikla eslestirebilir).
_TARGET_PRICE_LABELS = (
    "Hisse Başına Hedef Fiyat, TL",
    "Hedef Fiyat (TL)",
    "Target Price per Share, TRY",
    "Target Price (TRY)",
    "Hedef Fiyat, TL",
    "Target Price, TRY",
    "Hedef Fiyat",
    "Target Price",
)
_REFERENCE_PRICE_LABELS = (
    "Hisse Başına Fiyat, TL",
    "Price per Share, TRY",
    "Share Price, TRY",
    "Fiyat, TL",
    "Share Price",
)
_UPSIDE_LABELS = ("Getiri Potansiyeli", "Upside Potential", "Upside")
_RATING_LABELS = ("Öneri", "View", "Rating")

# Rapor tablosu "Bloomberg Ticker" satirindan sonra baslar; basliktaki
# ozet cumleler ayni kelimeleri (orn. "Getiri Potansiyeli") etiketsiz
# tekrar edebildigi icin arama bu pencereyle sinirlanir.
_FIELD_WINDOW_CHARS = 900

_TURKISH_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}


class _ProductListParser(HTMLParser):
    """PhillipCapital `arastirma-urunleri` liste sayfasindaki rapor kartlarini
    ayristirir (`<article class="product-item">` bloklari)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "article" and "product-item" in classes:
            self._current = {"date_text": "", "category": "", "title": "", "pdf_url": ""}
        elif self._current is not None and tag == "span" and "product-date" in classes:
            self._capture = "date_text"
        elif self._current is not None and tag == "span" and "product-category" in classes:
            self._capture = "category"
        elif self._current is not None and tag == "h3" and "product-title" in classes:
            self._capture = "title"
        elif self._current is not None and tag == "a" and "btn-review" in classes:
            self._current["pdf_url"] = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._capture:
            self._current[self._capture] = (self._current[self._capture] + data).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"span", "h3"}:
            self._capture = None
        elif tag == "article" and self._current is not None:
            if self._current.get("pdf_url"):
                self.items.append(self._current)
            self._current = None


def discover_reports(html: str) -> list[dict[str, str]]:
    parser = _ProductListParser()
    parser.feed(html)
    entries = []
    for item in parser.items:
        pdf_url = item["pdf_url"]
        if pdf_url.startswith("/"):
            pdf_url = PDF_BASE_URL + pdf_url
        entries.append({**item, "pdf_url": pdf_url})
    return entries


def max_listing_page(html: str) -> int:
    pages = [int(value) for value in _PAGE_LINK_RE.findall(html)]
    return max(pages) if pages else 1


def parse_listing_date(value: str) -> date:
    parts = value.strip().split()
    if len(parts) != 3:
        raise CollectorError(f"Gecersiz liste tarihi: {value!r}")
    day_text, month_text, year_text = parts
    month = _TURKISH_MONTHS.get(month_text.casefold())
    if month is None:
        raise CollectorError(f"Bilinmeyen Turkce ay adi: {month_text!r}")
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError as exc:
        raise CollectorError(f"Gecersiz liste tarihi: {value!r}") from exc


def report_guid(pdf_url: str) -> str:
    match = _GUID_RE.search(pdf_url)
    if match:
        return match.group(1)
    return hashlib.sha256(pdf_url.encode()).hexdigest()


def extract_first_page_text(pdf_bytes: bytes) -> str:
    """`pdftotext -layout` (poppler-utils) ile ilk sayfayi metne cevirir.

    Sutun hizasi bosluklarla korunuyor; alan ayristirma bu bosluklara
    dayaniyor (bkz. `_search_after_label`). pdfplumber'in layout modu
    denendi ama satir ici sutunlari tek bosluga sikistirdigi icin
    komsu sutun metnini deger sanma riski yuksekti (bu oturumda gercek
    PDF'lerle karsilastirmali olculdu) — pdftotext daha guvenilir cikti.
    """
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-f", "1", "-l", "1", "-", "-"],
            input=pdf_bytes,
            capture_output=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise CollectorError(f"pdftotext calistirilamadi: {exc}") from exc
    return proc.stdout.decode("utf-8", errors="replace")


def _search_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = re.compile(re.escape(label) + r"[ \t]{2,}(\S.*?)(?:[ \t]{2,}|\n|$)")
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _parse_amount(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    cleaned = raw.replace("%", "").replace("TL", "").replace("TRY", "").strip()
    if not cleaned or cleaned in {"-", "n.a.", "n.a", "N/A"}:
        return None
    has_comma = "," in cleaned
    has_dot = "." in cleaned
    if has_comma and has_dot:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _find_report_date(text: str) -> date | None:
    match = _HEADER_DATE_RE.search(text[:600])
    if not match:
        return None
    day, month, year = (int(group) for group in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_report_fields(
    text: str, *, pdf_url: str, title: str, listing_date: date
) -> dict[str, Any] | None:
    """Sayfa 1 metninden analist tavsiyesi alanlarini cikarir (saf fonksiyon).

    Bloomberg Ticker satiri bulunamazsa (eski/farkli sablon) None doner —
    isme dayali tahmin yapilmaz, satir sessizce atlanir. DB/PDF baytlarindan
    bagimsiz oldugu icin gercek `pdftotext -layout` ciktisi fixture'larina
    karsi DB'siz test edilir.
    """
    ticker_match = _TICKER_RE.search(text)
    if not ticker_match:
        return None
    window = text[ticker_match.start() : ticker_match.start() + _FIELD_WINDOW_CHARS]

    target_price = _parse_amount(_search_after_label(window, _TARGET_PRICE_LABELS))
    if target_price is None:
        return None

    reference_price = _parse_amount(_search_after_label(window, _REFERENCE_PRICE_LABELS))
    upside_pct = _parse_amount(_search_after_label(window, _UPSIDE_LABELS))
    rating_raw = _search_after_label(window, _RATING_LABELS)
    recommendation_date = _find_report_date(text) or listing_date

    return {
        "ticker": ticker_match.group(1).upper(),
        "source": SOURCE_NAME,
        "source_key": report_guid(pdf_url),
        "institution": INSTITUTION_NAME,
        "recommendation_raw": rating_raw or "Rapor Güncellemesi",
        "recommendation_normalized": normalize_recommendation(rating_raw or ""),
        "target_price": target_price,
        "reference_price": reference_price,
        "upside_pct": upside_pct,
        "recommendation_date": recommendation_date,
        "source_url": pdf_url,
        "raw_data": {
            "title": title,
            "category": CATEGORY,
            "listing_date": listing_date.isoformat(),
        },
    }


def parse_report_pdf(
    pdf_bytes: bytes, *, pdf_url: str, title: str, listing_date: date
) -> dict[str, Any] | None:
    """PDF baytlarini metne cevirir, alanlari cikarir ve checksum ekler."""
    text = extract_first_page_text(pdf_bytes)
    fields = parse_report_fields(text, pdf_url=pdf_url, title=title, listing_date=listing_date)
    if fields is None:
        return None
    fields["raw_data"]["pdf_sha256"] = hashlib.sha256(pdf_bytes).hexdigest()
    fields["raw_data"]["pdf_bytes"] = len(pdf_bytes)
    return fields


class InstitutionalReportCollector(BaseCollector):
    """PhillipCapital sirket raporlarini kesfeder, indirir, ayristirir."""

    name = "institutional_reports"

    def __init__(self, session: AsyncSession, *, max_pages: int | None = None) -> None:
        super().__init__(rate_limit_per_sec=1.0)
        self._session = session
        self._max_pages_override = max_pages

    async def run(self) -> dict:
        existing_keys = set(
            (
                await self._session.scalars(
                    select(AnalystRecommendation.source_key).where(
                        AnalystRecommendation.source == SOURCE_NAME
                    )
                )
            ).all()
        )
        active_tickers = set(
            (
                await self._session.scalars(
                    select(Instrument.ticker).where(Instrument.is_active.is_(True))
                )
            ).all()
        )
        # "Bloomberg Ticker" tasimayan eski/farkli sablonlar hicbir zaman DB'ye
        # yazilmaz (kabul edilen satir olusmaz); bu GUID'leri Redis'e
        # kaydetmezsek her koşuda ayni PDF'leri sonuçsuz yeniden indiririz —
        # ustelik sayfalamadaki erken-durma optimizasyonunu da bozar.
        redis = get_redis()
        cached_skip_guids = set(await redis.smembers(_SKIP_CACHE_KEY))
        known_keys = existing_keys | cached_skip_guids

        entries = await self._discover_all(known_keys)
        new_entries = {
            report_guid(entry["pdf_url"]): entry
            for entry in entries
            if report_guid(entry["pdf_url"]) not in known_keys
        }

        fetch_failures = 0
        skipped_unparseable = 0
        skipped_inactive_ticker = 0
        newly_skipped_guids: set[str] = set()
        mapped: list[dict[str, Any]] = []
        for guid, entry in new_entries.items():
            try:
                listing_date = parse_listing_date(entry["date_text"])
                pdf_bytes = await self.get_bytes(entry["pdf_url"])
            except Exception as exc:  # noqa: BLE001 - tek PDF hatasi batch'i durdurmasin
                fetch_failures += 1
                self.log.error(
                    "institutional_report_fetch_failed", pdf_url=entry["pdf_url"], error=str(exc)
                )
                continue
            fields = parse_report_pdf(
                pdf_bytes, pdf_url=entry["pdf_url"], title=entry["title"], listing_date=listing_date
            )
            if fields is None:
                skipped_unparseable += 1
                newly_skipped_guids.add(guid)
                continue
            if fields["ticker"] not in active_tickers:
                skipped_inactive_ticker += 1
                newly_skipped_guids.add(guid)
                continue
            mapped.append(fields)

        if newly_skipped_guids:
            await redis.sadd(_SKIP_CACHE_KEY, *newly_skipped_guids)

        if mapped:
            stmt = pg_insert(AnalystRecommendation).values(mapped)
            await self._session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_analyst_recommendation_source_key",
                    set_={
                        "recommendation_raw": stmt.excluded.recommendation_raw,
                        "recommendation_normalized": stmt.excluded.recommendation_normalized,
                        "target_price": stmt.excluded.target_price,
                        "reference_price": stmt.excluded.reference_price,
                        "upside_pct": stmt.excluded.upside_pct,
                        "raw_data": stmt.excluded.raw_data,
                        "fetched_at": func.now(),
                        "updated_at": func.now(),
                    },
                )
            )
            await self._session.commit()

        consensus = await recompute_analyst_consensus(self._session)
        return {
            "discovered": len(entries),
            "new": len(new_entries),
            "accepted": len(mapped),
            "skipped_unparseable_template": skipped_unparseable,
            "skipped_inactive_ticker": skipped_inactive_ticker,
            "fetch_failures": fetch_failures,
            "consensus": len(consensus),
        }

    async def _discover_all(self, existing_keys: set[str]) -> list[dict[str, str]]:
        first_page_html = (
            await self.get_bytes(LISTING_URL, params={"category": CATEGORY, "page": 1})
        ).decode("utf-8")
        max_page = max_listing_page(first_page_html)
        if self._max_pages_override:
            max_page = min(max_page, self._max_pages_override)

        def _has_new(page_entries: list[dict[str, str]]) -> bool:
            return any(report_guid(e["pdf_url"]) not in existing_keys for e in page_entries)

        current_page_entries = discover_reports(first_page_html)
        all_entries = list(current_page_entries)
        page = 1
        # Liste tarihe gore azalan sirali: bir sayfada hic yeni rapor yoksa
        # sonraki (daha eski) sayfalar da tamamen bilinen olacaktir —
        # gereksiz PDF listesi taramasi burada kesilir.
        while page < max_page and _has_new(current_page_entries):
            page += 1
            html = (
                await self.get_bytes(LISTING_URL, params={"category": CATEGORY, "page": page})
            ).decode("utf-8")
            current_page_entries = discover_reports(html)
            all_entries.extend(current_page_entries)
        return all_entries
