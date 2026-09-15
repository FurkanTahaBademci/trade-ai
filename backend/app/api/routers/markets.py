"""Piyasa geneli, sektorel analiz ve sirket karsilastirma endpoint'leri."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.exceptions import RedisError
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.core.sectors import resolve_sector
from app.models.fundamental import FundamentalSnapshot
from app.models.institutional import AnalystConsensus
from app.models.instrument import Instrument
from app.models.price import PriceDaily
from app.models.signal import CompositeSignalSnapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/heatmap")
async def get_market_heatmap(
    db: Annotated[AsyncSession, Depends(get_db)],
    min_volume: Annotated[float, Query(description="Minimum hacim filtresi (TRY)")] = 0.0,
    sector_filter: Annotated[str | None, Query(description="Belirli bir sektor filtresi")] = None,
) -> dict[str, Any]:
    """BIST hisselerinin sektorel agac haritasi ve gunluk performans dagilimi (Redis onbellekli)."""
    cache_key = f"markets:heatmap:{min_volume}:{sector_filter or 'all'}"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)

    # 1. Tum aktif hisseleri cek
    instruments_stmt = select(Instrument.ticker, Instrument.name).where(
        Instrument.is_active.is_(True)
    )
    inst_result = await db.execute(instruments_stmt)
    instruments = {row.ticker: row.name for row in inst_result}

    if not instruments:
        return {"as_of_date": None, "sectors": [], "summary": {}}

    # 2. Son 14 gunle sinirli fiyat barini cekerek gunluk % degisimi ve hacmi hesapla (97% daha az satir taramasi)
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
            WHERE date >= (SELECT COALESCE(MAX(date), CURRENT_DATE) - INTERVAL '14 days' FROM price_daily)
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
    signal_data = {
        row.ticker: {"score": row.composite_score, "label": row.signal_label}
        for row in signals_result
    }

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
        stocks.sort(key=lambda s: s["market_cap_try"] or s["volume_try"], reverse=True)
        total_vol = sum(s["volume_try"] for s in stocks)
        total_mc = sum(s["market_cap_try"] for s in stocks)

        if total_mc > 0:
            sec_avg_chg = sum(s["change_pct"] * (s["market_cap_try"] / total_mc) for s in stocks)
        else:
            sec_avg_chg = sum(s["change_pct"] for s in stocks) / len(stocks)

        sector_list.append(
            {
                "name": sec_name,
                "stock_count": len(stocks),
                "avg_change_pct": round(sec_avg_chg, 2),
                "total_volume_try": round(total_vol, 2),
                "total_market_cap_try": round(total_mc, 2),
                "stocks": stocks,
            }
        )

    sector_list.sort(key=lambda s: s["total_market_cap_try"], reverse=True)
    market_avg = round(sum(all_changes) / len(all_changes), 2) if all_changes else 0.0

    result = {
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

    try:
        await redis.setex(cache_key, 90, json.dumps(result))
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)

    return result


@router.get("/compare")
async def compare_companies(
    db: Annotated[AsyncSession, Depends(get_db)],
    tickers: Annotated[
        str, Query(description="Virgulle ayrilmis 2-4 hisse kodu (orn: THYAO,PGSUS)")
    ],
) -> dict[str, Any]:
    """2 ila 4 hisse senedinin temel, teknik, analist ve getiri karsilastirmasi (Peer Comparison)."""
    raw_tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    cleaned_tickers = list(dict.fromkeys(raw_tickers))[:4]

    if len(cleaned_tickers) < 2:
        raise HTTPException(
            status_code=400,
            detail="Karsilastirma icin en az 2 farkli hisse kodu belirtilmelidir (orn: THYAO,PGSUS)",
        )

    cache_key = f"markets:compare:{','.join(sorted(cleaned_tickers))}"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)

    # 1. Enstruman detaylari
    inst_stmt = select(Instrument).where(Instrument.ticker.in_(cleaned_tickers))
    inst_rows = (await db.scalars(inst_stmt)).all()
    inst_map = {inst.ticker: inst for inst in inst_rows}

    # 2. Fiyat ve performans gecmisi (Son 365 gun)
    one_year_ago = (datetime.now(UTC) - timedelta(days=365)).date()
    prices_stmt = (
        select(
            PriceDaily.ticker,
            PriceDaily.date,
            PriceDaily.close,
            PriceDaily.volume_try,
            PriceDaily.market_cap_try,
        )
        .where(PriceDaily.ticker.in_(cleaned_tickers), PriceDaily.date >= one_year_ago)
        .order_by(PriceDaily.date.asc())
    )
    prices_rows = (await db.execute(prices_stmt)).all()

    # Ticker bazli fiyat serisi ve metrikler
    ticker_price_series: dict[str, list[dict[str, Any]]] = {t: [] for t in cleaned_tickers}
    for row in prices_rows:
        ticker_price_series[row.ticker].append(
            {
                "date": row.date.isoformat(),
                "close": float(row.close),
                "volume_try": float(row.volume_try or 0.0),
                "market_cap_try": float(row.market_cap_try or 0.0),
            }
        )

    # 3. Temel Analiz Snapshot'lari (En son donem)
    fund_map: dict[str, FundamentalSnapshot] = {}
    for t in cleaned_tickers:
        f_stmt = (
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.ticker == t)
            .order_by(desc(FundamentalSnapshot.year), desc(FundamentalSnapshot.period))
            .limit(1)
        )
        f_row = await db.scalar(f_stmt)
        if f_row:
            fund_map[t] = f_row

    # 4. Analist Konsensuslari
    consensus_map: dict[str, AnalystConsensus] = {}
    for t in cleaned_tickers:
        c_stmt = (
            select(AnalystConsensus)
            .where(AnalystConsensus.ticker == t)
            .order_by(desc(AnalystConsensus.as_of_date))
            .limit(1)
        )
        c_row = await db.scalar(c_stmt)
        if c_row:
            consensus_map[t] = c_row

    # 5. Bilesik Sinyaller
    signal_map: dict[str, CompositeSignalSnapshot] = {}
    for t in cleaned_tickers:
        s_stmt = (
            select(CompositeSignalSnapshot)
            .where(CompositeSignalSnapshot.ticker == t)
            .order_by(desc(CompositeSignalSnapshot.as_of_date))
            .limit(1)
        )
        s_row = await db.scalar(s_stmt)
        if s_row:
            signal_map[t] = s_row

    # 6. Karsilastirma kartlari olustur
    companies: list[dict[str, Any]] = []
    for ticker in cleaned_tickers:
        inst = inst_map.get(ticker)
        p_series = ticker_price_series.get(ticker, [])
        fund = fund_map.get(ticker)
        cons = consensus_map.get(ticker)
        sig = signal_map.get(ticker)

        name = inst.name if inst else ticker
        sector = resolve_sector(ticker, name)

        last_price = p_series[-1]["close"] if p_series else 0.0
        prev_price = p_series[-2]["close"] if len(p_series) >= 2 else last_price
        change_1d_pct = (
            round(((last_price - prev_price) / prev_price) * 100.0, 2) if prev_price > 0 else 0.0
        )

        # 1 yillik ve 1 aylik getiri
        first_price = p_series[0]["close"] if p_series else last_price
        change_1y_pct = (
            round(((last_price - first_price) / first_price) * 100.0, 2) if first_price > 0 else 0.0
        )

        month_price = p_series[-22]["close"] if len(p_series) >= 22 else first_price
        change_1m_pct = (
            round(((last_price - month_price) / month_price) * 100.0, 2) if month_price > 0 else 0.0
        )

        latest_volume = p_series[-1]["volume_try"] if p_series else 0.0
        latest_mc = p_series[-1]["market_cap_try"] if p_series else 0.0

        # Finansal metrikler
        net_income = float(fund.net_income) if fund and fund.net_income else None
        revenue = float(fund.revenue) if fund and fund.revenue else None
        equity = float(fund.equity) if fund and fund.equity else None
        net_margin = float(fund.net_margin * 100) if fund and fund.net_margin is not None else None
        roe = float(fund.annualized_roe * 100) if fund and fund.annualized_roe is not None else None
        debt_to_equity = (
            float(fund.debt_to_equity) if fund and fund.debt_to_equity is not None else None
        )
        current_ratio = (
            float(fund.current_ratio) if fund and fund.current_ratio is not None else None
        )
        fundamental_score = (
            float(fund.fundamental_score) if fund and fund.fundamental_score is not None else None
        )

        # Tahmini F/K ve PD/DD
        pe_ratio = (
            round(latest_mc / net_income, 2)
            if (latest_mc > 0 and net_income and net_income > 0)
            else None
        )
        pb_ratio = (
            round(latest_mc / equity, 2) if (latest_mc > 0 and equity and equity > 0) else None
        )

        # Analist konsensus metrikleri
        target_price = float(cons.average_target) if cons and cons.average_target else None
        upside_pct = (
            float(cons.implied_upside_pct * 100)
            if cons and cons.implied_upside_pct is not None
            else None
        )
        rec_score = (
            float(cons.recommendation_score)
            if cons and cons.recommendation_score is not None
            else 50.0
        )
        buy_count = cons.buy_count if cons else 0
        hold_count = cons.hold_count if cons else 0
        sell_count = cons.sell_count if cons else 0

        # Sinyal metrikleri
        comp_score = float(sig.composite_score) if sig else 50.0
        sig_label = sig.signal_label if sig else "NEUTRAL"

        # 5 Eksenli Radar Puanlari (0 - 100 skalasi)
        val_score = 50.0
        if pe_ratio is not None:
            val_score = max(10.0, min(95.0, 100.0 - (pe_ratio * 3.0)))
        elif fundamental_score is not None:
            val_score = fundamental_score

        profit_score = 50.0
        if roe is not None:
            profit_score = max(15.0, min(95.0, roe * 1.5 + 20.0))
        elif fundamental_score is not None:
            profit_score = fundamental_score

        mom_score = max(10.0, min(95.0, 50.0 + change_1m_pct * 2.0))
        analyst_score = rec_score
        ai_score = comp_score

        companies.append(
            {
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "price": {
                    "last_price": last_price,
                    "change_1d_pct": change_1d_pct,
                    "change_1m_pct": change_1m_pct,
                    "change_1y_pct": change_1y_pct,
                    "volume_try": latest_volume,
                    "market_cap_try": latest_mc,
                },
                "multiples": {
                    "pe_ratio": pe_ratio,
                    "pb_ratio": pb_ratio,
                    "revenue_try": revenue,
                    "net_income_try": net_income,
                    "net_margin_pct": round(net_margin, 2) if net_margin is not None else None,
                    "roe_pct": round(roe, 2) if roe is not None else None,
                    "debt_to_equity": round(debt_to_equity, 2)
                    if debt_to_equity is not None
                    else None,
                    "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
                    "fundamental_score": round(fundamental_score, 1)
                    if fundamental_score is not None
                    else None,
                },
                "consensus": {
                    "target_price": target_price,
                    "upside_pct": round(upside_pct, 1) if upside_pct is not None else None,
                    "buy_count": buy_count,
                    "hold_count": hold_count,
                    "sell_count": sell_count,
                    "score": round(rec_score, 1),
                },
                "signal": {
                    "composite_score": round(comp_score, 1),
                    "label": sig_label,
                },
                "radar_scores": {
                    "valuation": round(val_score, 1),
                    "profitability": round(profit_score, 1),
                    "momentum": round(mom_score, 1),
                    "analysts": round(analyst_score, 1),
                    "ai_sentiment": round(ai_score, 1),
                },
            }
        )

    # 7. Normalize Getiri Zaman Serisi (Chart Icin)
    date_set: set[str] = set()
    for series in ticker_price_series.values():
        for pt in series:
            date_set.add(pt["date"])
    sorted_dates = sorted(date_set)

    first_prices = {}
    for t in cleaned_tickers:
        series = ticker_price_series.get(t, [])
        if series:
            first_prices[t] = series[0]["close"]

    normalized_chart: list[dict[str, Any]] = []
    step = max(1, len(sorted_dates) // 52)
    sample_dates = sorted_dates[::step]
    if sorted_dates and sorted_dates[-1] not in sample_dates:
        sample_dates.append(sorted_dates[-1])

    ticker_date_price_map = {
        t: {pt["date"]: pt["close"] for pt in ticker_price_series.get(t, [])}
        for t in cleaned_tickers
    }

    last_known = {t: first_prices.get(t, 1.0) for t in cleaned_tickers}
    for d in sample_dates:
        point: dict[str, Any] = {"date": d}
        for t in cleaned_tickers:
            price = ticker_date_price_map[t].get(d)
            if price is not None:
                last_known[t] = price
            base = first_prices.get(t, 1.0) or 1.0
            norm_val = round(((last_known[t] - base) / base) * 100.0, 2)
            point[t] = norm_val
        normalized_chart.append(point)

    response_payload = {
        "tickers": cleaned_tickers,
        "as_of_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "companies": companies,
        "normalized_chart": normalized_chart,
        "dimensions": [
            {"key": "valuation", "label": "Değerleme"},
            {"key": "profitability", "label": "Kârlılık"},
            {"key": "momentum", "label": "Momentum"},
            {"key": "analysts", "label": "Analistler"},
            {"key": "ai_sentiment", "label": "AI Sinyal"},
        ],
    }

    try:
        await redis.setex(cache_key, 60, json.dumps(response_payload))
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)

    return response_payload
