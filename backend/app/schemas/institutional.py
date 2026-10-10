"""Analist konsensusu ve TEFAS fon akimi API semalari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AnalystRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    source: str
    institution: str
    recommendation_raw: str
    recommendation_normalized: str
    target_price: float | None
    reference_price: float | None
    upside_pct: float | None
    recommendation_date: date
    source_url: str
    updated_at: datetime


class AnalystConsensusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    as_of_date: date
    institution_count: int
    buy_count: int
    hold_count: int
    sell_count: int
    review_count: int
    average_target: float | None
    median_target: float | None
    minimum_target: float | None
    maximum_target: float | None
    market_price: float | None
    implied_upside_pct: float | None
    target_dispersion: float | None
    recommendation_score: float | None
    average_age_days: float | None = None
    source_breakdown: dict
    computed_at: datetime


class FundSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_kind: str
    fund_code: str
    date: date
    fund_name: str
    price: float | None
    shares_outstanding: float | None
    investor_count: int | None
    portfolio_size: float | None
    stock_pct: float | None
    foreign_stock_pct: float | None
    estimated_net_flow: float | None
    estimated_stock_flow: float | None
    updated_at: datetime


class FundFlowAggregateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_kind: str
    date: date
    fund_count: int
    flow_observation_count: int
    total_aum: float
    total_net_flow: float | None
    total_stock_exposure: float
    estimated_stock_flow: float | None
    positive_flow_pct: float | None
    computed_at: datetime
