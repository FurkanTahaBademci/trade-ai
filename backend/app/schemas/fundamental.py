"""Finansal gercek ve temel analiz API ciktilari."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FinancialFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    financial_group: str
    exchange: str
    year: int
    period: int
    item_code: str
    item_name_tr: str
    item_name_en: str | None
    value: float
    updated_at: datetime


class FundamentalSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    financial_group: str
    exchange: str
    year: int
    period: int
    revenue: float | None
    gross_profit: float | None
    operating_profit: float | None
    ebitda_proxy: float | None
    net_income: float | None
    operating_cash_flow: float | None
    free_cash_flow: float | None
    current_assets: float | None
    cash: float | None
    current_liabilities: float | None
    short_term_debt: float | None
    long_term_debt: float | None
    equity: float | None
    revenue_yoy: float | None
    net_income_yoy: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    current_ratio: float | None
    debt_to_equity: float | None
    cash_to_debt: float | None
    annualized_roe: float | None
    operating_cash_flow_margin: float | None
    free_cash_flow_margin: float | None
    fundamental_score: float | None
    score_components: dict
    data_completeness: int
    computed_at: datetime
