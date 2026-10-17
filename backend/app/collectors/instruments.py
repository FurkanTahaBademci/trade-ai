"""Hisse evreni (instrument) toplayicisi.

Kaynak: KAP `GET /tr/api/company/items/IGS/A` — BIST'e kote (IGS tipi) tum
sirketlerin listesini tek istekte doner (~750+ kayit, sayfalama yok).
Endpoint gercek istekle dogrulandi; ornek yanit:
tests/fixtures/kap/company_items_sample.json.

Idempotency: `ticker` dogal anahtar uzerinden upsert (ON CONFLICT DO UPDATE).
Bu collector'i N kez calistirmak veritabaninda ayni satirlari gunceller,
kopya satir uretmez.
"""

from __future__ import annotations

import re

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, chunked, dedupe_last
from app.models import Instrument

KAP_COMPANY_ITEMS_URL = "https://www.kap.org.tr/tr/api/company/items/IGS/A"
KAP_REFERER = "https://www.kap.org.tr/tr/bist-sirketler"
# KAP satirinda islem goren payla ayni sirkete bagli gelen ama piyasada
# fiilen islem gormeyen pay siniflari ve KAP'in test uyesi. Evrene girerlerse
# milyon TL'lik nominal fiyat, anlamsiz F/K ve kopya analist hedefiyle
# skorlanirlar.
EXCLUDED_TICKERS = frozenset(
    {
        "ISATR",  # Is Bankasi A grubu
        "ISBTR",  # Is Bankasi B grubu
        "ISKUR",  # Is Bankasi kurucu payi
        "KTEST",  # KAP test bildirimi uyesi
    }
)


def map_kap_item_to_instrument_fields(item: dict) -> list[dict]:
    """Bir KAP sirket satirini bir veya daha cok `instrument` satirina cevirir.

    Hisse kodu olmayan uyeler (bagimsiz denetim sirketleri, "-" stockCode)
    icin bos liste doner. KAP ayni sirketin farkli pay siniflarini
    `KRDMA, KRDMB, KRDMD` gibi tek alanda verebildiginden her kod ayri satira
    donusturulur.

    Hisse evrenine yalniz borsada payi islem goren kodlar aktif girer:
    - `payIslemDurumu == "0"`: paylar islem gormez (faktoring, yalniz tahvil
      ihrac eden bankalar vb.).
    - Ayni satirdaki 3 harfli kodlar (`A1CAP, ACP`; `GARAN, TGB`) borclanma
      araci ihracci kodudur; BIST pay kodlari 4-5 harflidir.
    - `EXCLUDED_TICKERS`: islem gormeyen pay siniflari ve test uyesi.
    Saf fonksiyon oldugu icin
    DB/ag olmadan test edilebilir (bkz. tests/test_instrument_mapping.py).
    """
    raw_tickers = str(item.get("stockCode") or "").strip().upper()
    tickers = list(
        dict.fromkeys(
            ticker
            for ticker in re.split(r"[,;/\s]+", raw_tickers)
            if ticker and ticker != "-"
        )
    )
    if not tickers:
        return []

    member_active = item.get("kapMemberState") == "A"
    shares_traded = str(item.get("payIslemDurumu", "1")) != "0"
    common_fields = {
        "name": (item.get("kapMemberTitle") or "").strip(),
        "city": item.get("cityName"),
        "kap_member_oid": item["kapMemberOid"],
        "mkk_member_oid": item.get("mkkMemberOid"),
    }
    return [
        {
            "ticker": ticker,
            **common_fields,
            "is_active": member_active
            and shares_traded
            and len(ticker) >= 4
            and ticker not in EXCLUDED_TICKERS,
        }
        for ticker in tickers
    ]


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

        rows: list[dict] = []
        skipped_no_ticker = 0

        for item in raw_items:
            instrument_rows = map_kap_item_to_instrument_fields(item)
            if not instrument_rows:
                skipped_no_ticker += 1
                continue
            rows.extend(instrument_rows)

        # Ayni kod iki uyede gorunurse eski satir-satir upsert'teki gibi sonuncusu yazilir.
        for batch in chunked(dedupe_last(rows, lambda row: row["ticker"]), 1_000):
            stmt = pg_insert(Instrument).values(list(batch))
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
        created_or_updated = len(rows)

        await self._session.commit()

        return {
            "total_kap_members": len(raw_items),
            "upserted": created_or_updated,
            "skipped_no_ticker": skipped_no_ticker,
        }
