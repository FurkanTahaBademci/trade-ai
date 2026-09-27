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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.core.config import get_settings
from app.models import Instrument, PriceDaily

DEFAULT_BACKFILL_YEARS = 3
DEFAULT_CHUNK_SIZE = 10

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
    if isinstance(ts, date_type) and not isinstance(ts, datetime):
        mapped["date"] = ts
    elif hasattr(ts, "date"):
        mapped["date"] = ts.date()
    elif isinstance(ts, str):
        try:
            if "-" in ts:
                parts = ts.split("-")
                if len(parts[0]) == 4:
                    mapped["date"] = date_type.fromisoformat(ts)
                else:
                    day, month, year = (int(part) for part in parts)
                    mapped["date"] = date_type(year, month, day)
            else:
                mapped["date"] = date_type.fromisoformat(ts)
        except (ValueError, TypeError):
            return None
    return mapped


class PriceCollector(BaseCollector):
    """IS Yatirim API / `isyatirimhisse` uzerinden EOD fiyat ceker, `price_daily`'ye upsert eder."""

    name = "prices"

    def __init__(
        self,
        session: AsyncSession,
        tickers: list[str] | None = None,
        start_date: date_type | None = None,
        end_date: date_type | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__()
        settings = get_settings()
        today = datetime.now(ZoneInfo(settings.tz)).date()
        self._session = session
        self._tickers = tickers
        self._start_date = start_date or (today - timedelta(days=365 * DEFAULT_BACKFILL_YEARS))
        self._end_date = end_date or today
        self._chunk_size = chunk_size or getattr(settings, "price_collector_chunk_size", DEFAULT_CHUNK_SIZE)
        self._local_client = None

    async def _get_client(self):
        if self._client is not None:
            return self._client
        if self._local_client is None:
            import httpx

            settings = get_settings()
            self._local_client = httpx.AsyncClient(
                headers={"User-Agent": settings.collector_user_agent},
                timeout=getattr(settings, "price_collector_timeout", 30),
                verify=False,
            )
        return self._local_client

    async def _close_local_client(self) -> None:
        if self._local_client is not None:
            await self._local_client.aclose()
            self._local_client = None

    async def _active_tickers(self) -> list[str]:
        result = await self._session.execute(
            select(Instrument.ticker).where(Instrument.is_active.is_(True))
        )
        return [row[0] for row in result.all()]

    async def _fetch_ticker_data(self, client, ticker: str, start_str: str, end_str: str) -> list[dict]:
        url = (
            f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil"
            f"?hisse={ticker}&startdate={start_str}&enddate={end_str}"
        )
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if isinstance(data, dict):
                return data.get("value", []) or []
            return []
        except Exception as exc:  # noqa: BLE001
            self.log.warning("ticker_price_fetch_failed", ticker=ticker, error=str(exc))
            return []

    async def run(self) -> dict:
        tickers = self._tickers or await self._active_tickers()
        if not tickers:
            return {"tickers": 0, "rows_upserted": 0, "note": "instrument tablosu bos — once InstrumentCollector calistir"}

        start_str = self._start_date.strftime("%d-%m-%Y")
        end_str = self._end_date.strftime("%d-%m-%Y")

        total_rows = 0
        failed_tickers: list[str] = []

        chunks = [tickers[i : i + self._chunk_size] for i in range(0, len(tickers), self._chunk_size)]
        client = await self._get_client()

        try:
            for chunk_idx, chunk in enumerate(chunks, start=1):
                tasks = [self._fetch_ticker_data(client, ticker, start_str, end_str) for ticker in chunk]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                chunk_records: list[dict] = []
                for ticker, res in zip(chunk, results, strict=False):
                    if isinstance(res, Exception):
                        self.log.warning("price_ticker_failed", ticker=ticker, error=str(res))
                        failed_tickers.append(ticker)
                    elif isinstance(res, list):
                        chunk_records.extend(res)
                    else:
                        failed_tickers.append(ticker)

                if not chunk_records:
                    self.log.info("price_chunk_empty", chunk_index=chunk_idx, of=len(chunks), tickers=chunk)
                    continue

                rows = [
                    mapped
                    for record in chunk_records
                    if (mapped := map_price_record(record)) is not None
                ]

                if not rows:
                    continue

                try:
                    insert_batch_size = 1000
                    for offset in range(0, len(rows), insert_batch_size):
                        batch = rows[offset : offset + insert_batch_size]
                        stmt = pg_insert(PriceDaily).values(batch)
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
                except Exception as exc:  # noqa: BLE001
                    await self._session.rollback()
                    self.log.error("price_chunk_db_failed", chunk_index=chunk_idx, error=str(exc))
                    failed_tickers.extend(chunk)
                    continue
        finally:
            await self._close_local_client()

        return {
            "tickers_requested": len(tickers),
            "rows_upserted": total_rows,
            "failed_tickers": failed_tickers,
        }
