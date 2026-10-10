"""KAP bildirim toplayicisi.

Akis:
1. Son birkac gunun bildirim listesini tek POST istegiyle al.
2. Liste metadatasini `disclosure_index` uzerinden upsert et.
3. Yalnizca yeni veya detayi daha once alinamamis bildirimlerin detayini cek.
4. Ek metadata'sini (objId, dosya adi, uzanti) `kap_attachment` tablosuna kaydet.

Idempotency: bildirim icin `disclosure_index`, ek icin KAP `objId` dogal
anahtardir. Ayni pencere ikinci kez toplandiginda yeni satir olusmaz ve daha
once basariyla indirilen detay icin tekrar ag istegi atilmaz.
"""

from __future__ import annotations

import re
import struct
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import ClassVar
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectorError, settings
from app.market_calendar.event_dates import disclosure_event_date
from app.models import Instrument, KapAttachment, KapDisclosure

KAP_DISCLOSURE_LIST_URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
KAP_DETAIL_URL = "https://www.kap.org.tr/tr/api/notification/attachment-detail/{index}"
KAP_FILE_URL = "https://www.kap.org.tr/tr/api/file/download/{obj_id}"
KAP_SEARCH_REFERER = "https://www.kap.org.tr/tr/bildirim-sorgu"

DEFAULT_LOOKBACK_DAYS = 3
KAP_RESULT_LIMIT = 2000
# Bir gunun bildirim sayisi limite carparsa uye OID'lerine gore bu boyutta
# parcalara bolunup ayri ayri sorgulanir (bkz. _fetch_day).
KAP_MEMBER_CHUNK_SIZE = 150
ISTANBUL = ZoneInfo("Europe/Istanbul")


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]

# ObjectOutputStream ile yazilmis Java `byte[]` class descriptor'i. Hemen
# ardindan 4-byte signed big-endian uzunluk ve dosyanin kendisi gelir.
_JAVA_BYTE_ARRAY_PREFIX = bytes.fromhex(
    "aced0005"  # STREAM_MAGIC + STREAM_VERSION
    "75"  # TC_ARRAY
    "72"  # TC_CLASSDESC
    "0002"  # UTF class-name length
    "5b42"  # "[B"
    "acf317f8060854e0"  # byte[] serialVersionUID
    "02"  # SC_SERIALIZABLE
    "0000"  # field count
    "78"  # TC_ENDBLOCKDATA
    "70"  # TC_NULL (super class)
)


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().upper() in {"Y", "YES", "TRUE", "1"}
    return bool(value)


def parse_kap_datetime(value: str) -> datetime:
    """KAP'in liste ve detayda kullandigi iki tarih biçimini normalize et."""
    value = value.strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=ISTANBUL)
        except ValueError:
            pass
    raise CollectorError(f"KAP tarih formati taninmadi: {value!r}")


def parse_ticker_codes(value: object) -> list[str]:
    """`TSK, TSKB` gibi KAP kod alanini sirali, tekrarsiz listeye cevir."""
    if not isinstance(value, str):
        return []
    codes: list[str] = []
    for part in re.split(r"[,;/\s]+", value.upper().strip()):
        code = part.strip()
        if code and code != "-" and code not in codes:
            codes.append(code)
    return codes


def map_disclosure_list_item(item: dict) -> dict:
    """KAP liste satirini model alanlarina ceviren saf fonksiyon."""
    index = item.get("disclosureIndex") or item.get("basicDisclosureIndex")
    published_at = item.get("publishDate")
    if index is None or not published_at:
        raise CollectorError(
            f"KAP liste satirinda disclosureIndex/publishDate eksik: alanlar={sorted(item.keys())}"
        )

    return {
        "disclosure_index": int(index),
        "published_at": parse_kap_datetime(str(published_at)),
        "kap_title": str(item.get("kapTitle") or "").strip(),
        "subject": (str(item["subject"]).strip() if item.get("subject") else None),
        "summary": (str(item["summary"]).strip() if item.get("summary") else None),
        "disclosure_class": item.get("disclosureClass"),
        "disclosure_type": item.get("disclosureType"),
        "disclosure_category": item.get("disclosureCategory"),
        "ticker_codes": parse_ticker_codes(item.get("stockCodes")),
        "is_late": _as_bool(item.get("isLate")),
        "has_multi_language_support": _as_bool(item.get("hasMultiLanguageSupport")),
        "attachment_count": int(item.get("attachmentCount") or 0),
        "raw_list_item": item,
    }


class _VisibleTextParser(HTMLParser):
    """KAP HTML'indeki gizli Ingilizce hucreleri atmali basit metin cikarici."""

    _BLOCK_TAGS: ClassVar[set[str]] = {"br", "div", "li", "p", "table", "td", "th", "tr"}
    _VOID_TAGS: ClassVar[set[str]] = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden_stack: list[bool] = []

    @property
    def _hidden(self) -> bool:
        return self._hidden_stack[-1] if self._hidden_stack else False

    @staticmethod
    def _element_is_hidden(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())
        style = re.sub(r"\s+", "", attr_map.get("style", "").lower())
        return tag in {"script", "style"} or "content-en" in classes or "display:none" in style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        hidden = self._hidden or self._element_is_hidden(tag, attrs)
        if not hidden and tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        if tag not in self._VOID_TAGS:
            self._hidden_stack.append(hidden)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        hidden = self._hidden or self._element_is_hidden(tag, attrs)
        if not hidden and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        hidden = self._hidden
        if not hidden and tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        if self._hidden_stack:
            self._hidden_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)


def html_to_visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_detail_response(payload: dict | list) -> dict:
    if isinstance(payload, list):
        if not payload or not isinstance(payload[0], dict):
            raise CollectorError("KAP detay yaniti bos veya gecersiz liste")
        return payload[0]
    if isinstance(payload, dict):
        return payload
    raise CollectorError(f"KAP detay yanit tipi gecersiz: {type(payload).__name__}")


def map_disclosure_detail(payload: dict | list) -> dict:
    """Detay yanitindan ham HTML, gorunur Turkce metin ve ek listesini cikar."""
    detail = normalize_detail_response(payload)
    bodies = detail.get("disclosureBody") or []
    if isinstance(bodies, str):
        bodies = [bodies]
    html_parts = [part for part in bodies if isinstance(part, str)]
    body_html = "\n".join(html_parts) or None
    body_text = html_to_visible_text(body_html) if body_html else None

    attachments = detail.get("attachments") or []
    if not isinstance(attachments, list):
        raise CollectorError("KAP detay attachments alani liste degil")

    return {
        "body_html": body_html,
        "body_text": body_text,
        "raw_detail": detail,
        "attachments": attachments,
    }


def map_attachment_metadata(disclosure_index: int, item: dict) -> dict:
    obj_id = str(item.get("objId") or "").strip()
    if not obj_id:
        raise CollectorError(f"KAP ekinde objId eksik: {item!r}")
    file_name = str(item.get("fileName") or obj_id).strip()
    extension = item.get("fileExtension")
    return {
        "obj_id": obj_id,
        "disclosure_index": disclosure_index,
        "file_name": file_name,
        "file_extension": str(extension).lower().lstrip(".") if extension else None,
        "raw_metadata": item,
    }


def unwrap_java_serialized_byte_array(data: bytes) -> bytes:
    """KAP dosya yanitindaki Java serialization katmanini dogrulayip kaldir."""
    if not data:
        raise CollectorError("KAP ek indirme yaniti bos")
    if not data.startswith(b"\xac\xed\x00\x05"):
        # Kaynak ileride ham dosya dondurmeye baslarsa geriye uyumlu davran.
        return data
    if not data.startswith(_JAVA_BYTE_ARRAY_PREFIX):
        raise CollectorError("KAP eki Java serialization, fakat byte[] semasi taninmadi")

    length_offset = len(_JAVA_BYTE_ARRAY_PREFIX)
    if len(data) < length_offset + 4:
        raise CollectorError("KAP eki Java byte[] uzunlugu okunamadi")
    length = struct.unpack(">i", data[length_offset : length_offset + 4])[0]
    if length < 0:
        raise CollectorError("KAP eki null Java byte[] olarak geldi")
    payload = data[length_offset + 4 :]
    if len(payload) != length:
        raise CollectorError(
            f"KAP eki uzunluk uyusmazligi: beklenen={length}, gelen={len(payload)}"
        )
    return payload


class KapCollector(BaseCollector):
    name = "kap"

    def __init__(
        self,
        session: AsyncSession,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        end_date: date | None = None,
    ) -> None:
        super().__init__(rate_limit_per_sec=settings.kap_rate_limit_per_sec)
        if lookback_days < 1:
            raise ValueError("lookback_days en az 1 olmali")
        self._session = session
        self._lookback_days = lookback_days
        self._end_date = end_date or datetime.now(ISTANBUL).date()

    async def _fetch_list(self) -> list[dict]:
        start_date = self._end_date - timedelta(days=self._lookback_days - 1)
        all_items: dict[int, dict] = {}
        query_date = start_date
        while query_date <= self._end_date:
            for item in await self._fetch_day(query_date):
                index = item.get("disclosureIndex") or item.get("basicDisclosureIndex")
                if index is None:
                    raise CollectorError(f"KAP liste satirinda index eksik: {item!r}")
                all_items[int(index)] = item
            query_date += timedelta(days=1)
        return list(all_items.values())

    async def _post_list(self, query_date: date, member_oids: list[str]) -> list[dict]:
        payload = {
            "fromDate": query_date.isoformat(),
            "toDate": query_date.isoformat(),
            "mkkMemberOidList": member_oids,
            "subjectList": [],
        }
        data = await self.post_json(
            KAP_DISCLOSURE_LIST_URL,
            json=payload,
            headers={"Referer": KAP_SEARCH_REFERER, "Content-Type": "application/json"},
        )
        if not isinstance(data, list):
            raise CollectorError(f"KAP liste yaniti liste degil: {type(data).__name__}")
        return data

    async def _active_member_oids(self) -> list[str]:
        result = await self._session.scalars(
            select(Instrument.kap_member_oid).where(Instrument.is_active.is_(True)).distinct()
        )
        return sorted({oid for oid in result.all() if oid})

    async def _fetch_day(self, query_date: date) -> list[dict]:
        """Bir gunun bildirim listesini ceker.

        KAP tek istekte en fazla `KAP_RESULT_LIMIT` kayit dondurur; asilirsa
        fazlasi sessizce kaybolur. Bu durumda gunun sorgusu, evrendeki aktif
        uye OID'lerine gore parcalara bolunup ayri ayri tekrarlanir, boylece
        tek bir yogun gun veri kaybina yol acmadan tamamlanir.
        """

        data = await self._post_list(query_date, [])
        if len(data) < KAP_RESULT_LIMIT:
            return data

        member_oids = await self._active_member_oids()
        if not member_oids:
            raise CollectorError(
                f"KAP gunluk liste limiti doldu ({len(data)}); {query_date} icin "
                "veri kaybi riski var (aktif uye listesi bos, bolme yapilamadi)"
            )
        self.log.warning(
            "kap_daily_limit_hit_splitting_by_member",
            query_date=query_date.isoformat(),
            member_count=len(member_oids),
        )
        merged: dict[int, dict] = {}
        for chunk in _chunk(member_oids, KAP_MEMBER_CHUNK_SIZE):
            chunk_data = await self._post_list(query_date, chunk)
            if len(chunk_data) >= KAP_RESULT_LIMIT:
                raise CollectorError(
                    f"KAP uye-bazli bolme sonrasi da limit doldu ({query_date}, "
                    f"{len(chunk)} uyelik parca); KAP_MEMBER_CHUNK_SIZE dusurulmeli"
                )
            for item in chunk_data:
                index = item.get("disclosureIndex") or item.get("basicDisclosureIndex")
                if index is not None:
                    merged[int(index)] = item
        return list(merged.values())

    async def _save_detail(self, disclosure_index: int, payload: dict | list) -> int:
        mapped = map_disclosure_detail(payload)
        headline = (
            await self._session.execute(
                select(
                    KapDisclosure.kap_title, KapDisclosure.subject, KapDisclosure.disclosure_class
                ).where(KapDisclosure.disclosure_index == disclosure_index)
            )
        ).first()
        event = None
        if headline is not None:
            event = disclosure_event_date(
                title=headline.kap_title,
                subject=headline.subject,
                disclosure_class=headline.disclosure_class,
                body_text=mapped["body_text"],
            )
        await self._session.execute(
            update(KapDisclosure)
            .where(KapDisclosure.disclosure_index == disclosure_index)
            .values(
                body_html=mapped["body_html"],
                body_text=mapped["body_text"],
                raw_detail=mapped["raw_detail"],
                event_date=event.event_date if event else None,
                event_detail=event.detail if event else None,
                updated_at=func.now(),
            )
        )

        attachments_count = 0
        for item in mapped["attachments"]:
            fields = map_attachment_metadata(disclosure_index, item)
            stmt = pg_insert(KapAttachment).values(**fields)
            stmt = stmt.on_conflict_do_update(
                index_elements=[KapAttachment.obj_id],
                set_={
                    "disclosure_index": stmt.excluded.disclosure_index,
                    "file_name": stmt.excluded.file_name,
                    "file_extension": stmt.excluded.file_extension,
                    "raw_metadata": stmt.excluded.raw_metadata,
                },
            )
            await self._session.execute(stmt)
            attachments_count += 1
        await self._session.commit()
        return attachments_count

    async def run(self) -> dict:
        raw_items = await self._fetch_list()
        # Savunmaci dedup: KAP ayni index'i birden cok kez dondururse tek
        # upsert/detay istegi yap. Son gorulen metadata guncel kabul edilir.
        by_index = {
            mapped["disclosure_index"]: mapped
            for item in raw_items
            if (mapped := map_disclosure_list_item(item))
        }
        mapped_items = list(by_index.values())
        indices = [item["disclosure_index"] for item in mapped_items]

        existing_details: dict[int, dict | None] = {}
        if indices:
            result = await self._session.execute(
                select(KapDisclosure.disclosure_index, KapDisclosure.raw_detail).where(
                    KapDisclosure.disclosure_index.in_(indices)
                )
            )
            existing_details = {row[0]: row[1] for row in result.all()}

        for fields in mapped_items:
            stmt = pg_insert(KapDisclosure).values(**fields)
            stmt = stmt.on_conflict_do_update(
                index_elements=[KapDisclosure.disclosure_index],
                set_={
                    "published_at": stmt.excluded.published_at,
                    "kap_title": stmt.excluded.kap_title,
                    "subject": stmt.excluded.subject,
                    "summary": stmt.excluded.summary,
                    "disclosure_class": stmt.excluded.disclosure_class,
                    "disclosure_type": stmt.excluded.disclosure_type,
                    "disclosure_category": stmt.excluded.disclosure_category,
                    "ticker_codes": stmt.excluded.ticker_codes,
                    "is_late": stmt.excluded.is_late,
                    "has_multi_language_support": stmt.excluded.has_multi_language_support,
                    "attachment_count": stmt.excluded.attachment_count,
                    "raw_list_item": stmt.excluded.raw_list_item,
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(stmt)
        await self._session.commit()

        detail_fetched = 0
        detail_failures: list[int] = []
        attachments_saved = 0
        new_count = sum(index not in existing_details for index in indices)

        for index in indices:
            if index in existing_details and existing_details[index] is not None:
                continue
            try:
                detail_payload = await self.get_json(
                    KAP_DETAIL_URL.format(index=index),
                    headers={"Referer": f"https://www.kap.org.tr/tr/Bildirim/{index}"},
                )
                saved_count = await self._save_detail(index, detail_payload)
                attachments_saved += saved_count
                detail_fetched += 1
            except Exception as exc:  # noqa: BLE001 - sonraki bildirimleri toplamaya devam et
                await self._session.rollback()
                detail_failures.append(index)
                self.log.error("kap_detail_failed", disclosure_index=index, error=str(exc))

        return {
            "listed": len(mapped_items),
            "new": new_count,
            "details_fetched": detail_fetched,
            "detail_failures": detail_failures,
            "attachments_saved": attachments_saved,
        }
