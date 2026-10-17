"""Piyasa geneli, sektorel analiz ve sirket karsilastirma endpoint'leri."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from redis.exceptions import RedisError
from sqlalchemy import desc, func, select, text
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import csv_response
from app.core.db import get_db
from app.core.redis import get_redis
from app.core.sectors import resolve_sector
from app.core.valuation import price_multiple, trailing_net_income
from app.models.fundamental import FundamentalSnapshot
from app.models.institutional import AnalystConsensus
from app.models.instrument import Instrument
from app.models.price import PriceDaily
from app.models.signal import CompositeSignalSnapshot
from app.schemas.screener import ScreenerOut, ScreenerRowOut
from app.screener.service import SORT_FIELDS, ScreenerFilters, load_screener_rows, screen_rows
from app.signals.service import MODEL_VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/heatmap")
async def get_market_heatmap(
    db: Annotated[AsyncSession, Depends(get_db)],
    min_volume: Annotated[float, Query(description="Minimum hacim filtresi (TRY)")] = 0.0,
    sector_filter: Annotated[str | None, Query(description="Belirli bir sektör filtresi")] = None,
) -> dict[str, Any]:
    """BIST hisselerinin sektörel ağaç haritası ve günlük performans dağılımı (Redis önbellekli)."""

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

    # 3. Son skor gununun sinyalleri. Tum skor gecmisi uzerinde ROW_NUMBER
    # (her gun ~600 satir buyuyen tablo) yerine yalniz son gun indeksle okunur.
    latest_signal_date = await db.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == MODEL_VERSION
        )
    )
    signals_result = (
        await db.execute(
            select(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.signal_label,
            ).where(
                CompositeSignalSnapshot.as_of_date == latest_signal_date,
                CompositeSignalSnapshot.model_version == MODEL_VERSION,
            )
        )
        if latest_signal_date
        else []
    )
    signal_data = {
        row.ticker: {"score": float(row.composite_score), "label": row.signal_label}
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

        # Skoru olmayan hisseye sahte "50 / Notr" yazilmaz; arayuz "—" gosterir.
        sig = signal_data.get(ticker, {"score": None, "label": None})

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



def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def compare_valuation_empty() -> dict[str, Any]:
    return {
        "pe_ratio": None,
        "pb_ratio": None,
        "ttm_net_income_try": None,
        "ttm_revenue_try": None,
        "net_margin_pct": None,
        "roe_pct": None,
        "ttm_basis": None,
        "fundamental_period": None,
    }


def compare_valuation(
    *,
    year: int,
    period: int,
    net_income: float | None,
    revenue: float | None,
    equity: float | None,
    market_cap: float | None,
    net_income_history: dict[tuple[int, int], float | None],
    revenue_history: dict[tuple[int, int], float | None],
) -> dict[str, Any]:
    """Karsilastirma tablosundaki F/K, PD/DD, ROE ve net marji tek tabandan uretir.

    F/K tarayicidaki kuralla ayni: son 12 ay net kari ile; zarar veya negatif
    ozsermayede gosterilmez. ROE ve net marj da ayni son 12 ay karindan
    hesaplanir; aksi halde mevsimsel bir ceyrek zarari yilliklandirilip
    pozitif F/K'nin yaninda negatif ROE gorunur (F/K x ROE = PD/DD bozulur).
    """
    ttm_net_income, basis = trailing_net_income(
        year=year, period=period, net_income=net_income, history=net_income_history
    )
    # Hasilat da yil ici kumulatif; ayni TTM formulu gecerli.
    ttm_revenue, _ = trailing_net_income(
        year=year, period=period, net_income=revenue, history=revenue_history
    )
    pe = price_multiple(market_cap, ttm_net_income)
    pb = price_multiple(market_cap, equity)
    roe = (
        ttm_net_income / equity * 100
        if ttm_net_income is not None and equity is not None and equity > 0
        else None
    )
    net_margin = (
        ttm_net_income / ttm_revenue * 100
        if ttm_net_income is not None and ttm_revenue is not None and ttm_revenue > 0
        else None
    )
    return {
        "pe_ratio": round(pe, 2) if pe is not None else None,
        "pb_ratio": round(pb, 2) if pb is not None else None,
        "ttm_net_income_try": ttm_net_income,
        "ttm_revenue_try": ttm_revenue,
        "net_margin_pct": round(net_margin, 2) if net_margin is not None else None,
        "roe_pct": round(roe, 2) if roe is not None else None,
        # "annual" | "ttm" | "annualized": arayuz etiketi icin hesap tabani.
        "ttm_basis": basis,
        "fundamental_period": f"{year}/{period}",
    }


@router.get("/compare")
async def compare_companies(
    db: Annotated[AsyncSession, Depends(get_db)],
    tickers: Annotated[
        str, Query(description="Virgülle ayrılmış 2-4 hisse kodu (örn: THYAO,PGSUS)")
    ],
) -> dict[str, Any]:
    """2 ila 4 hisse senedinin temel, teknik, analist ve getiri karşılaştırması (Peer Comparison)."""
    def _normalize_ticker(t: str) -> str:
        return t.strip().replace("İ", "I").replace("i", "I").replace("ı", "I").upper()

    raw_tickers = [_normalize_ticker(t) for t in tickers.split(",") if t.strip()]
    cleaned_tickers = list(dict.fromkeys(raw_tickers))[:4]

    if len(cleaned_tickers) < 2:
        raise HTTPException(
            status_code=400,
            detail="Karşılaştırma için en az 2 farklı hisse kodu belirtilmelidir (örn: THYAO,PGSUS)",
        )


    cache_key = f"markets:compare:v2:{','.join(sorted(cleaned_tickers))}"
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

    # 3. Temel Analiz Snapshot'lari: en son donem + TTM kar icin onceki yil donemleri
    fund_map: dict[str, FundamentalSnapshot] = {}
    net_income_history: dict[str, dict[tuple[int, int], float | None]] = {}
    revenue_history: dict[str, dict[tuple[int, int], float | None]] = {}
    f_rows = (
        await db.scalars(
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.ticker.in_(cleaned_tickers))
            .order_by(desc(FundamentalSnapshot.year), desc(FundamentalSnapshot.period))
        )
    ).all()
    for f_row in f_rows:
        latest_row = fund_map.setdefault(f_row.ticker, f_row)
        if f_row.financial_group == latest_row.financial_group:
            net_income_history.setdefault(f_row.ticker, {})[(f_row.year, f_row.period)] = (
                float(f_row.net_income) if f_row.net_income is not None else None
            )
            revenue_history.setdefault(f_row.ticker, {})[(f_row.year, f_row.period)] = (
                float(f_row.revenue) if f_row.revenue is not None else None
            )

    # 4. Analist konsensuslari ve 5. bilesik sinyaller: hisse basina ayri sorgu
    # yerine tek sorguda her hissenin en guncel satiri.
    consensus_map: dict[str, AnalystConsensus] = {
        row.ticker: row
        for row in (
            await db.scalars(
                select(AnalystConsensus)
                .where(AnalystConsensus.ticker.in_(cleaned_tickers))
                .ext(distinct_on(AnalystConsensus.ticker))
                .order_by(AnalystConsensus.ticker, desc(AnalystConsensus.as_of_date))
            )
        ).all()
    }
    signal_map: dict[str, CompositeSignalSnapshot] = {
        row.ticker: row
        for row in (
            await db.scalars(
                select(CompositeSignalSnapshot)
                .where(
                    CompositeSignalSnapshot.ticker.in_(cleaned_tickers),
                    CompositeSignalSnapshot.model_version == MODEL_VERSION,
                )
                .ext(distinct_on(CompositeSignalSnapshot.ticker))
                .order_by(CompositeSignalSnapshot.ticker, desc(CompositeSignalSnapshot.as_of_date))
            )
        ).all()
    }

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
        net_income = _optional_float(fund.net_income) if fund else None
        revenue = _optional_float(fund.revenue) if fund else None
        debt_to_equity = _optional_float(fund.debt_to_equity) if fund else None
        current_ratio = _optional_float(fund.current_ratio) if fund else None
        fundamental_score = _optional_float(fund.fundamental_score) if fund else None
        valuation = (
            compare_valuation(
                year=fund.year,
                period=fund.period,
                net_income=net_income,
                revenue=revenue,
                equity=_optional_float(fund.equity),
                market_cap=latest_mc,
                net_income_history=net_income_history.get(ticker, {}),
                revenue_history=revenue_history.get(ticker, {}),
            )
            if fund
            else compare_valuation_empty()
        )
        pe_ratio = valuation["pe_ratio"]
        roe = valuation["roe_pct"]

        # Analist konsensus metrikleri
        target_price = float(cons.average_target) if cons and cons.average_target else None
        # implied_upside_pct zaten yuzde birimindedir (64.5 = %64,5).
        upside_pct = (
            float(cons.implied_upside_pct)
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
                    **valuation,
                    "revenue_try": revenue,
                    "net_income_try": net_income,
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


# --- Hisse tarayici ----------------------------------------------------------

SCREENER_CACHE_KEY = "markets:screener:v1"
SCREENER_LABELS = {"VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"}


def screener_filters(
    q: Annotated[str | None, Query(max_length=64, description="Kod veya şirket adı")] = None,
    sector: Annotated[str | None, Query(max_length=64)] = None,
    label: Annotated[list[str] | None, Query(description="Sinyal etiketi; tekrarlanabilir")] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    max_pe: Annotated[float | None, Query(gt=0)] = None,
    max_pb: Annotated[float | None, Query(gt=0)] = None,
    min_roe: Annotated[float | None, Query(description="Yüzde, ör. 25")] = None,
    min_revenue_growth: Annotated[float | None, Query(description="Yüzde")] = None,
    min_upside: Annotated[float | None, Query(description="Yüzde")] = None,
    min_change_1m: Annotated[float | None, Query(description="Yüzde")] = None,
    min_market_cap: Annotated[float | None, Query(ge=0, description="TRY")] = None,
    sort: Annotated[str, Query(pattern=f"^({'|'.join(SORT_FIELDS)})$")] = "composite_score",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ScreenerFilters:
    labels = tuple(item for item in (label or []) if item in SCREENER_LABELS)
    if label and not labels:
        raise HTTPException(status_code=422, detail="Geçersiz sinyal etiketi.")
    return ScreenerFilters(
        query=q,
        sector=sector,
        labels=labels,
        min_score=min_score,
        max_pe=max_pe,
        max_pb=max_pb,
        min_roe=min_roe,
        min_revenue_growth=min_revenue_growth,
        min_upside=min_upside,
        min_change_1m=min_change_1m,
        min_market_cap=min_market_cap,
        sort=sort,
        order=order,
        limit=limit,
    )


async def _screener_dataset(db: AsyncSession) -> dict[str, Any]:
    """Tum evrenin tarayici satirlari; fiyat/skor gun icinde seyrek degistigi icin 5 dk onbellek."""
    redis = get_redis()
    try:
        cached = await redis.get(SCREENER_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)
    as_of, rows = await load_screener_rows(db)
    payload = {"as_of_date": as_of.isoformat() if as_of else None, "rows": rows}
    try:
        await redis.setex(SCREENER_CACHE_KEY, 300, json.dumps(payload))
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)
    return payload


@router.get("/screener", response_model=ScreenerOut)
async def stock_screener(
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[ScreenerFilters, Depends(screener_filters)],
) -> ScreenerOut:
    """Skor, degerleme, karlilik, buyume, momentum ve analist kriterleriyle hisse tarama."""
    dataset = await _screener_dataset(db)
    matched = screen_rows(dataset["rows"], filters)
    return ScreenerOut(
        as_of_date=dataset["as_of_date"],
        total=len(dataset["rows"]),
        matched=len(matched),
        sectors=sorted({row["sector"] for row in dataset["rows"]}),
        rows=[ScreenerRowOut.model_validate(row) for row in matched[: filters.limit]],
    )


@router.get("/screener.csv")
async def stock_screener_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[ScreenerFilters, Depends(screener_filters)],
) -> Response:
    dataset = await _screener_dataset(db)
    rows = screen_rows(dataset["rows"], filters)[: filters.limit]
    columns = [
        ("ticker", "Hisse"),
        ("name", "Şirket"),
        ("sector", "Sektör"),
        ("last_price", "Son fiyat"),
        ("change_1d_pct", "Günlük %"),
        ("change_1m_pct", "1 ay %"),
        ("change_3m_pct", "3 ay %"),
        ("market_cap_try", "Piyasa değeri"),
        ("composite_score", "Bileşik skor"),
        ("signal_label", "Etiket"),
        ("pe_ratio", "F/K (TTM)"),
        ("pb_ratio", "PD/DD"),
        ("roe_pct", "ROE %"),
        ("revenue_yoy_pct", "Gelir büyümesi %"),
        ("net_income_yoy_pct", "Net kâr büyümesi %"),
        ("upside_pct", "Analist potansiyeli %"),
        ("fundamental_period", "Finansal dönem"),
    ]
    return csv_response(
        f"tarayici-{dataset['as_of_date'] or 'bos'}.csv",
        [label for _, label in columns],
        [[row.get(key) for key, _ in columns] for row in rows],
    )
