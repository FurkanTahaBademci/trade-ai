"""Hisse tarayici API ciktilari. Yuzdeler yuzde birimindedir (25.0 = %25)."""

from pydantic import BaseModel


class ScreenerRowOut(BaseModel):
    ticker: str
    name: str | None
    sector: str
    price_date: str
    last_price: float
    change_1d_pct: float | None
    change_1m_pct: float | None
    change_3m_pct: float | None
    volume_try: float | None
    market_cap_try: float | None
    composite_score: float | None
    signal_label: str | None
    confidence: float | None
    fundamental_period: str | None
    fundamental_score: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    roe_pct: float | None
    revenue_yoy_pct: float | None
    net_income_yoy_pct: float | None
    net_margin_pct: float | None
    debt_to_equity: float | None
    upside_pct: float | None
    analyst_score: float | None
    analyst_count: int | None


class ScreenerOut(BaseModel):
    as_of_date: str | None
    total: int
    matched: int
    sectors: list[str]
    rows: list[ScreenerRowOut]
