"""Gunluk fiyat (EOD) toplayicisi.

Kaynak: `isyatirimhisse.fetch_stock_data` (senkron/blocking kutuphane —
`asyncio.to_thread` ile sarmalaniyor). Kutuphane ticker basina ayri HTTP
istegi atiyor (~0.4-0.5 sn/ticker, bu oturumda olculdu — bkz.
.claude/PROGRESS.md Faz 1 notlari), bu yuzden ~600 hisseyi tek cagrida
istemek yerine `chunk_size` ile parcalara bolup ilerleme loglaniyor.

Kolon eslemesi icin app/models/price.py dosyasindaki docstring'e bak.

Idempotency: (ticker, date) dogal anahtari uzerinden upsert. Ayni tarih
araligi icin collector'i tekrar calistirmak mevcut satirlari gunceller,
kopya uretmez.
"""

from __future__ import annotations

import asyncio
from datetime import date as date_type
from datetime import timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.models import Instrument, PriceDaily

DEFAULT_BACKFILL_YEARS = 3
DEFAULT_CHUNK_SIZE = 50

# isyatirimhisse ham kolon adlari -> price_daily model alanlari
_COLUMN_MAP = {
    "HGDG_HS_KODU": "ticker",
    "HGDG_TARIH": "date",
    "HGDG_KAPANIS": "close",
    "HGDG_MAX": "high",
    "HGDG_MIN": "low",
    "HGDG_AOF": "avg_price",
    "HGDG_HACIM": "volume_try",
    "DOLAR_BAZLI_FIYAT": "close_usd",
    "PD": "market_cap_try",
}


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


def map_price_record(record: dict) -> dict | None:
    """isyatirimhisse'den gelen tek bir satiri `price_daily` alanlarina cevirir.

    ticker/date/close eksikse None doner (kullanilamaz satir). Saf fonksiyon
    oldugu icin DB/ag olmadan test edilebilir (bkz. tests/test_price_mapping.py).
    """
    mapped = {_COLUMN_MAP[k]: _clean(v) for k, v in record.items() if k in _COLUMN_MAP}
    if not mapped.get("ticker") or not mapped.get("date") or mapped.get("close") is None:
        return None
    ts = mapped["date"]
    mapped["date"] = ts.date() if hasattr(ts, "date") else ts
    return mapped


class PriceCollector(BaseCollector):
    """`isyatirimhisse` uzerinden EOD fiyat ceker, `price_daily`'ye upsert eder."""

    name = "prices"

    def __init__(
        self,
        session: AsyncSession,
        tickers: list[str] | None = None,
        start_date: date_type | None = None,
        end_date: date_type | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        super().__init__()
        self._session = session
        self._tickers = tickers
        self._start_date = start_date or (date_type.today() - timedelta(days=365 * DEFAULT_BACKFILL_YEARS))
        self._end_date = end_date or date_type.today()
        self._chunk_size = chunk_size

    async def _active_tickers(self) -> list[str]:
        result = await self._session.execute(
            select(Instrument.ticker).where(Instrument.is_active.is_(True))
        )
        return [row[0] for row in result.all()]

    async def run(self) -> dict:
        # Gec import: isyatirimhisse import'u agir olabilir, sadece bu collector
        # calisirken yuklensin.
        from isyatirimhisse import fetch_stock_data

        tickers = self._tickers or await self._active_tickers()
        if not tickers:
            return {"tickers": 0, "rows_upserted": 0, "note": "instrument tablosu bos — once InstrumentCollector calistir"}

        start_str = self._start_date.strftime("%d-%m-%Y")
        end_str = self._end_date.strftime("%d-%m-%Y")

        total_rows = 0
        failed_chunks: list[str] = []

        chunks = [tickers[i : i + self._chunk_size] for i in range(0, len(tickers), self._chunk_size)]

        for chunk_idx, chunk in enumerate(chunks, start=1):
            try:
                df = await asyncio.to_thread(fetch_stock_data, chunk, start_str, end_str)
            except Exception as exc:  # noqa: BLE001 - bir chunk basarisiz olsa bile digerleri devam etsin
                self.log.error("price_chunk_failed", chunk_index=chunk_idx, tickers=chunk, error=str(exc))
                failed_chunks.extend(chunk)
                continue

            if df is None or df.empty:
                continue

            rows = [
                mapped
                for record in df.to_dict(orient="records")
                if (mapped := map_price_record(record)) is not None
            ]

            if not rows:
                continue

            stmt = pg_insert(PriceDaily).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_price_daily_ticker_date",
                set_={
                    "close": stmt.excluded.close,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "avg_price": stmt.excluded.avg_price,
                    "volume_try": stmt.excluded.volume_try,
                    "close_usd": stmt.excluded.close_usd,
                    "market_cap_try": stmt.excluded.market_cap_try,
                },
            )
            await self._session.execute(stmt)
            await self._session.commit()

            total_rows += len(rows)
            self.log.info("price_chunk_done", chunk_index=chunk_idx, of=len(chunks), rows=len(rows))

        return {
            "tickers_requested": len(tickers),
            "rows_upserted": total_rows,
            "failed_tickers": failed_chunks,
        }
