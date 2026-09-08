"""BIST100 (XU100) gunluk endeks degeri toplayicisi.

Kaynak: `isyatirimhisse.fetch_index_data` (senkron/blocking — `asyncio.to_thread`
ile sarmalanir, bkz. collectors/prices.py ile ayni desen).

Idempotency: (index_code, date) dogal anahtari uzerinden upsert. Ayni tarih
araligi icin tekrar calistirmak mevcut satirlari gunceller, kopya uretmez.
"""

from __future__ import annotations

import asyncio
from datetime import date as date_type
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.models import IndexDaily

DEFAULT_BACKFILL_YEARS = 3
DEFAULT_INDEX_CODES = ("XU100",)


def _clean(value):
    """pandas NaN/NaT degerlerini SQL NULL'a (None) cevirir."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def map_index_record(record: dict) -> dict | None:
    """isyatirimhisse.fetch_index_data satirini `index_daily` alanlarina cevirir.

    index_code/date/value eksikse None doner. Saf fonksiyon oldugu icin
    DB/ag olmadan test edilebilir (bkz. tests/test_index_price_mapping.py).
    """
    index_code = _clean(record.get("INDEX"))
    raw_date = _clean(record.get("DATE"))
    value = _clean(record.get("VALUE"))
    if not index_code or raw_date is None or value is None:
        return None
    date_value = raw_date.date() if hasattr(raw_date, "date") else raw_date
    return {"index_code": str(index_code), "date": date_value, "value": float(value)}


class IndexPriceCollector(BaseCollector):
    """`isyatirimhisse.fetch_index_data` uzerinden BIST100 degerini ceker."""

    name = "index_prices"

    def __init__(
        self,
        session: AsyncSession,
        index_codes: tuple[str, ...] = DEFAULT_INDEX_CODES,
        start_date: date_type | None = None,
        end_date: date_type | None = None,
    ) -> None:
        super().__init__()
        today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
        self._session = session
        self._index_codes = index_codes
        self._start_date = start_date or (today - timedelta(days=365 * DEFAULT_BACKFILL_YEARS))
        self._end_date = end_date or today

    async def run(self) -> dict:
        # Gec import: isyatirimhisse import'u agir olabilir, sadece bu
        # collector calisirken yuklensin (prices.py ile ayni desen).
        from isyatirimhisse import fetch_index_data

        start_str = self._start_date.strftime("%d-%m-%Y")
        end_str = self._end_date.strftime("%d-%m-%Y")

        try:
            df = await asyncio.to_thread(
                fetch_index_data, list(self._index_codes), start_str, end_str
            )
        except Exception as exc:
            self.log.error("index_price_fetch_failed", indices=self._index_codes, error=str(exc))
            raise

        if df is None or df.empty:
            return {"index_codes": list(self._index_codes), "rows_upserted": 0}

        rows = [
            mapped
            for record in df.to_dict(orient="records")
            if (mapped := map_index_record(record)) is not None
        ]
        if not rows:
            return {"index_codes": list(self._index_codes), "rows_upserted": 0}

        stmt = pg_insert(IndexDaily).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_index_daily_code_date",
            set_={"value": stmt.excluded.value},
        )
        await self._session.execute(stmt)
        await self._session.commit()

        return {"index_codes": list(self._index_codes), "rows_upserted": len(rows)}
