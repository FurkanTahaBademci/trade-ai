"""Cok kriterli hisse tarayici: tum evren icin tek satirlik ozet + saf filtre/siralama.

Veri bes kaynaktan birlestirilir (fiyat, bilesik skor, temel analiz, analist
konsensusu, hisse evreni). Yukleme pahali oldugu icin router tum veri setini
kisa sure onbellege alir; filtre ve siralama `screen_rows` ile bellekte yapilir.
Yuzdeler `_pct` sonekiyle yuzde biriminde doner (25.0 = %25).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sectors import resolve_sector
from app.core.valuation import price_multiple, trailing_net_income
from app.models import AnalystConsensus, CompositeSignalSnapshot, FundamentalSnapshot, Instrument
from app.signals.service import MODEL_VERSION

# Islem gunu sayisi: ~1 ay ve ~3 ay.
MONTH_ROWS = 21
QUARTER_ROWS = 63

SORT_FIELDS = (
    "ticker",
    "composite_score",
    "change_1d_pct",
    "change_1m_pct",
    "change_3m_pct",
    "market_cap_try",
    "volume_try",
    "pe_ratio",
    "pb_ratio",
    "roe_pct",
    "revenue_yoy_pct",
    "net_income_yoy_pct",
    "upside_pct",
)


@dataclass(frozen=True)
class ScreenerFilters:
    query: str | None = None
    sector: str | None = None
    labels: tuple[str, ...] = ()
    min_score: float | None = None
    max_pe: float | None = None
    max_pb: float | None = None
    min_roe: float | None = None
    min_revenue_growth: float | None = None
    min_upside: float | None = None
    min_change_1m: float | None = None
    min_market_cap: float | None = None
    sort: str = "composite_score"
    order: str = "desc"
    limit: int = 100

    def bounds(self) -> list[tuple[str, float | None, float | None]]:
        """(alan, alt sinir, ust sinir); sinir verilen alani bos olan satir elenir."""
        return [
            ("composite_score", self.min_score, None),
            ("pe_ratio", None, self.max_pe),
            ("pb_ratio", None, self.max_pb),
            ("roe_pct", self.min_roe, None),
            ("revenue_yoy_pct", self.min_revenue_growth, None),
            ("upside_pct", self.min_upside, None),
            ("change_1m_pct", self.min_change_1m, None),
            ("market_cap_try", self.min_market_cap, None),
        ]


def screen_rows(rows: list[dict[str, Any]], filters: ScreenerFilters) -> list[dict[str, Any]]:
    """Filtreleri uygular ve siralar. Filtre verilen alani bos olan satir elenir;
    siralamada bos degerler yonden bagimsiz en sona kalir."""
    needle = (filters.query or "").strip().casefold()
    sector = (filters.sector or "").strip().casefold()
    labels = set(filters.labels)
    matched = []
    for row in rows:
        if needle and needle not in row["ticker"].casefold() and needle not in (
            row.get("name") or ""
        ).casefold():
            continue
        if sector and (row.get("sector") or "").casefold() != sector:
            continue
        if labels and row.get("signal_label") not in labels:
            continue
        if not all(
            _within(row.get(name), low, high)
            for name, low, high in filters.bounds()
            if low is not None or high is not None
        ):
            continue
        matched.append(row)

    key = filters.sort if filters.sort in SORT_FIELDS else "composite_score"
    descending = filters.order != "asc"
    present = [row for row in matched if row.get(key) is not None]
    missing = [row for row in matched if row.get(key) is None]
    present.sort(key=lambda row: row["ticker"])
    present.sort(key=lambda row: row[key], reverse=descending)
    missing.sort(key=lambda row: row["ticker"])
    return present + missing


def _within(value: Any, low: float | None, high: float | None) -> bool:
    if value is None:
        return False
    if low is not None and value < low:
        return False
    return not (high is not None and value > high)


def _pct(value: Any) -> float | None:
    return round(float(value) * 100, 2) if value is not None else None


def _change(current: float | None, previous: float | None) -> float | None:
    if current is None or not previous:
        return None
    return round((current / previous - 1) * 100, 2)


async def load_screener_rows(session: AsyncSession) -> tuple[date | None, list[dict[str, Any]]]:
    instruments = dict(
        (
            await session.execute(
                select(Instrument.ticker, Instrument.name).where(Instrument.is_active.is_(True))
            )
        ).all()
    )
    if not instruments:
        return None, []

    # Son ~100 takvim gununden 1., 2., 22. ve 64. islem gunu kapanislari.
    price_rows = (
        await session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT ticker, date, close, volume_try, market_cap_try,
                           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
                    FROM price_daily
                    WHERE date >= (SELECT COALESCE(MAX(date), CURRENT_DATE) FROM price_daily)
                                  - INTERVAL '100 days'
                )
                SELECT ticker, rn, date, CAST(close AS FLOAT) AS close,
                       CAST(volume_try AS FLOAT) AS volume_try,
                       CAST(market_cap_try AS FLOAT) AS market_cap_try
                FROM ranked
                WHERE rn IN (1, 2, :month_rn, :quarter_rn)
                """
            ),
            {"month_rn": MONTH_ROWS + 1, "quarter_rn": QUARTER_ROWS + 1},
        )
    ).all()
    prices: dict[str, dict[int, Any]] = {}
    for row in price_rows:
        prices.setdefault(row.ticker, {})[row.rn] = row

    signal_date = await session.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == MODEL_VERSION
        )
    )
    signals = {
        row.ticker: row
        for row in (
            await session.execute(
                select(
                    CompositeSignalSnapshot.ticker,
                    CompositeSignalSnapshot.composite_score,
                    CompositeSignalSnapshot.signal_label,
                    CompositeSignalSnapshot.confidence,
                ).where(
                    CompositeSignalSnapshot.as_of_date == signal_date,
                    CompositeSignalSnapshot.model_version == MODEL_VERSION,
                )
            )
        ).all()
    }

    fundamentals: dict[str, Any] = {}
    net_income_history: dict[str, dict[tuple[int, int], float | None]] = {}
    for row in (
        await session.execute(
            select(
                FundamentalSnapshot.ticker,
                FundamentalSnapshot.financial_group,
                FundamentalSnapshot.year,
                FundamentalSnapshot.period,
                FundamentalSnapshot.net_income,
                FundamentalSnapshot.equity,
                FundamentalSnapshot.revenue_yoy,
                FundamentalSnapshot.net_income_yoy,
                FundamentalSnapshot.net_margin,
                FundamentalSnapshot.annualized_roe,
                FundamentalSnapshot.debt_to_equity,
                FundamentalSnapshot.fundamental_score,
            ).order_by(
                FundamentalSnapshot.ticker,
                FundamentalSnapshot.year.desc(),
                FundamentalSnapshot.period.desc(),
            )
        )
    ).all():
        latest = fundamentals.setdefault(row.ticker, row)
        if row.financial_group == latest.financial_group:
            net_income_history.setdefault(row.ticker, {})[(row.year, row.period)] = (
                float(row.net_income) if row.net_income is not None else None
            )

    consensus = {
        row.ticker: row
        for row in (
            await session.execute(
                select(
                    AnalystConsensus.ticker,
                    AnalystConsensus.implied_upside_pct,
                    AnalystConsensus.recommendation_score,
                    AnalystConsensus.institution_count,
                )
                .distinct(AnalystConsensus.ticker)
                .order_by(AnalystConsensus.ticker, AnalystConsensus.as_of_date.desc())
            )
        ).all()
    }

    latest_price_date: date | None = None
    rows: list[dict[str, Any]] = []
    for ticker, name in instruments.items():
        points = prices.get(ticker, {})
        last = points.get(1)
        if last is None or not last.close:
            continue
        latest_price_date = max(latest_price_date or last.date, last.date)
        previous = points.get(2)
        month = points.get(MONTH_ROWS + 1)
        quarter = points.get(QUARTER_ROWS + 1)
        signal = signals.get(ticker)
        fundamental = fundamentals.get(ticker)
        view = consensus.get(ticker)
        market_cap = last.market_cap_try or None

        ttm = None
        if fundamental is not None:
            ttm, _ = trailing_net_income(
                year=fundamental.year,
                period=fundamental.period,
                net_income=(
                    float(fundamental.net_income) if fundamental.net_income is not None else None
                ),
                history=net_income_history.get(ticker, {}),
            )
        pe = price_multiple(market_cap, ttm)
        pb = price_multiple(
            market_cap,
            float(fundamental.equity) if fundamental and fundamental.equity is not None else None,
        )
        rows.append(
            {
                "ticker": ticker,
                "name": name,
                "sector": resolve_sector(ticker, name),
                "price_date": last.date.isoformat(),
                "last_price": last.close,
                "change_1d_pct": _change(last.close, previous.close if previous else None),
                "change_1m_pct": _change(last.close, month.close if month else None),
                "change_3m_pct": _change(last.close, quarter.close if quarter else None),
                "volume_try": last.volume_try,
                "market_cap_try": market_cap,
                "composite_score": float(signal.composite_score) if signal else None,
                "signal_label": signal.signal_label if signal else None,
                "confidence": float(signal.confidence) if signal else None,
                "fundamental_period": (
                    f"{fundamental.year}/{fundamental.period}" if fundamental else None
                ),
                "fundamental_score": (
                    float(fundamental.fundamental_score)
                    if fundamental and fundamental.fundamental_score is not None
                    else None
                ),
                "pe_ratio": round(pe, 2) if pe is not None else None,
                "pb_ratio": round(pb, 2) if pb is not None else None,
                "roe_pct": _pct(fundamental.annualized_roe) if fundamental else None,
                "revenue_yoy_pct": _pct(fundamental.revenue_yoy) if fundamental else None,
                "net_income_yoy_pct": _pct(fundamental.net_income_yoy) if fundamental else None,
                "net_margin_pct": _pct(fundamental.net_margin) if fundamental else None,
                "debt_to_equity": (
                    round(float(fundamental.debt_to_equity), 2)
                    if fundamental and fundamental.debt_to_equity is not None
                    else None
                ),
                # Konsensus tablosundaki deger zaten yuzde biriminde (64.5 = %64,5).
                "upside_pct": (
                    round(float(view.implied_upside_pct), 2)
                    if view and view.implied_upside_pct is not None
                    else None
                ),
                "analyst_score": (
                    float(view.recommendation_score)
                    if view and view.recommendation_score is not None
                    else None
                ),
                "analyst_count": view.institution_count if view else None,
            }
        )
    return latest_price_date, rows
