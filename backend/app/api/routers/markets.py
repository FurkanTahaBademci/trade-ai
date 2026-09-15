"""Piyasa geneli ve sektorel analiz endpoint'leri."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sectors import resolve_sector
from app.models.instrument import Instrument

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/heatmap")
async def get_market_heatmap(
    min_volume: float = Query(0.0, description="Minimum hacim filtresi (TRY)"),
    sector_filter: str | None = Query(None, description="Belirli bir sektor filtresi"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """BIST hisselerinin sektorel agac haritasi ve gunluk performans dagilimi."""
    # 1. Tum aktif hisseleri cek
    instruments_stmt = select(Instrument.ticker, Instrument.name).where(Instrument.is_active.is_(True))
    inst_result = await db.execute(instruments_stmt)
    instruments = {row.ticker: row.name for row in inst_result}

    if not instruments:
        return {"as_of_date": None, "sectors": [], "summary": {}}

    # 2. Son 2 fiyat barini cekerek gunluk % degisimi ve hacmi hesapla
    prices_query = text("""
        WITH ranked_prices AS (
            SELECT
                ticker,
                date,
                close,
                volume_try,
                market_cap_try,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
            FROM price_daily
        )
        SELECT
            p1.ticker,
            CAST(p1.close AS FLOAT) as last_close,
            CAST(p2.close AS FLOAT) as prev_close,
            CAST(p1.volume_try AS FLOAT) as volume_try,
            CAST(p1.market_cap_try AS FLOAT) as market_cap_try,
            p1.date as as_of_date
        FROM ranked_prices p1
        LEFT JOIN ranked_prices p2 ON p1.ticker = p2.ticker AND p2.rn = 2
        WHERE p1.rn = 1;
    """)
    prices_result = await db.execute(prices_query)
    price_data: dict[str, dict[str, Any]] = {}
    latest_date = None

    for row in prices_result:
        ticker = row.ticker
        last_close = row.last_close or 0.0
        prev_close = row.prev_close or last_close
        change_pct = 0.0
        if prev_close and prev_close > 0:
            change_pct = round(((last_close - prev_close) / prev_close) * 100.0, 2)

        if row.as_of_date and (latest_date is None or row.as_of_date > latest_date):
            latest_date = row.as_of_date

        price_data[ticker] = {
            "last_price": last_close,
            "change_pct": change_pct,
            "volume_try": row.volume_try or 0.0,
            "market_cap_try": row.market_cap_try or 0.0,
        }

    # 3. En son sinyal snapshot'larini cek
    signals_query = text("""
        WITH ranked_signals AS (
            SELECT
                ticker,
                CAST(composite_score AS FLOAT) as composite_score,
                signal_label,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY as_of_date DESC) as rn
            FROM composite_signal_snapshot
        )
        SELECT ticker, composite_score, signal_label
        FROM ranked_signals
        WHERE rn = 1;
    """)
    signals_result = await db.execute(signals_query)
    signal_data = {row.ticker: {"score": row.composite_score, "label": row.signal_label} for row in signals_result}

    # 4. Sektorlere gore grupla
    sector_buckets: dict[str, list[dict[str, Any]]] = {}
    pos_count = 0
    neg_count = 0
    neutral_count = 0
    all_changes: list[float] = []

    for ticker, name in instruments.items():
        p = price_data.get(ticker)
        if not p or p["last_price"] <= 0:
            continue

        if min_volume > 0 and p["volume_try"] < min_volume:
            continue

        sector = resolve_sector(ticker, name)
        if sector_filter and sector.lower() != sector_filter.lower():
            continue

        chg = p["change_pct"]
        all_changes.append(chg)
        if chg > 0:
            pos_count += 1
        elif chg < 0:
            neg_count += 1
        else:
            neutral_count += 1

        sig = signal_data.get(ticker, {"score": 50.0, "label": "NEUTRAL"})

        stock_item = {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "last_price": p["last_price"],
            "change_pct": chg,
            "volume_try": p["volume_try"],
            "market_cap_try": p["market_cap_try"],
            "composite_score": sig["score"],
            "signal_label": sig["label"],
        }

        sector_buckets.setdefault(sector, []).append(stock_item)

    # 5. Sektor istatistiklerini hesapla ve siralama yap
    sector_list = []
    for sec_name, stocks in sector_buckets.items():
        # Siralama: market_cap veya volume buyuklugune gore
        stocks.sort(key=lambda s: (s["market_cap_try"] or s["volume_try"]), reverse=True)
        total_vol = sum(s["volume_try"] for s in stocks)
        total_mc = sum(s["market_cap_try"] for s in stocks)

        # Agirlikli veya aritmetik ortalama getiri
        if total_mc > 0:
            sec_avg_chg = sum(s["change_pct"] * (s["market_cap_try"] / total_mc) for s in stocks)
        else:
            sec_avg_chg = sum(s["change_pct"] for s in stocks) / len(stocks)

        sector_list.append({
            "name": sec_name,
            "stock_count": len(stocks),
            "avg_change_pct": round(sec_avg_chg, 2),
            "total_volume_try": round(total_vol, 2),
            "total_market_cap_try": round(total_mc, 2),
            "stocks": stocks,
        })

    # Sektorleri hisse sayisi ve toplam buyuklugune gore sirala
    sector_list.sort(key=lambda s: s["total_market_cap_try"], reverse=True)

    market_avg = round(sum(all_changes) / len(all_changes), 2) if all_changes else 0.0

    return {
        "as_of_date": latest_date.isoformat() if latest_date else None,
        "sectors": sector_list,
        "summary": {
            "total_instruments": len(all_changes),
            "positive_count": pos_count,
            "negative_count": neg_count,
            "neutral_count": neutral_count,
            "market_avg_change_pct": market_avg,
        },
    }
