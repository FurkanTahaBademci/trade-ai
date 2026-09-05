"""Hisse evreni (instrument) toplayicisi.

Kaynak: KAP `GET /tr/api/company/items/IGS/A` — BIST'e kote (IGS tipi) tum
sirketlerin listesini tek istekte doner (~750+ kayit, sayfalama yok).
Endpoint smoke_sources.py disinda, bu oturumda ayrica dogrulandi
(bkz. .claude/PROGRESS.md Faz 1 notlari).

Idempotency: `ticker` dogal anahtar uzerinden upsert (ON CONFLICT DO UPDATE).
Bu collector'i N kez calistirmak veritabaninda ayni satirlari gunceller,
kopya satir uretmez.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.models import Instrument

KAP_COMPANY_ITEMS_URL = "https://www.kap.org.tr/tr/api/company/items/IGS/A"
KAP_REFERER = "https://www.kap.org.tr/tr/bist-sirketler"


def map_kap_item_to_instrument_fields(item: dict) -> dict | None:
    """Bir KAP `company/items/IGS/A` satirini `instrument` alanlarina cevirir.

    Hisse kodu olmayan uyeler (bagimsiz denetim sirketleri, "-" stockCode)
    icin None doner — cagiran taraf bunu atlamali. Saf fonksiyon oldugu icin
    DB/ag olmadan test edilebilir (bkz. tests/test_instrument_mapping.py).
    """
    ticker = (item.get("stockCode") or "").strip().upper()
    if not ticker or ticker == "-":
        return None

    return {
        "ticker": ticker,
        "name": (item.get("kapMemberTitle") or "").strip(),
        "city": item.get("cityName"),
        "kap_member_oid": item["kapMemberOid"],
        "mkk_member_oid": item.get("mkkMemberOid"),
        "is_active": item.get("kapMemberState") == "A",
    }


class InstrumentCollector(BaseCollector):
    """KAP'tan BIST hisse evrenini ceker ve `instrument` tablosuna upsert eder."""

    name = "instruments"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    async def run(self) -> dict:
        raw_items = await self.get_json(
            KAP_COMPANY_ITEMS_URL,
            headers={"Referer": KAP_REFERER},
        )

        created_or_updated = 0
        skipped_no_ticker = 0

        for item in raw_items:
            fields = map_kap_item_to_instrument_fields(item)
            if fields is None:
                skipped_no_ticker += 1
                continue

            stmt = pg_insert(Instrument).values(**fields)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Instrument.ticker],
                set_={
                    "name": stmt.excluded.name,
                    "city": stmt.excluded.city,
                    "kap_member_oid": stmt.excluded.kap_member_oid,
                    "mkk_member_oid": stmt.excluded.mkk_member_oid,
                    "is_active": stmt.excluded.is_active,
                },
            )
            await self._session.execute(stmt)
            created_or_updated += 1

        await self._session.commit()

        return {
            "total_kap_members": len(raw_items),
            "upserted": created_or_updated,
            "skipped_no_ticker": skipped_no_ticker,
        }
