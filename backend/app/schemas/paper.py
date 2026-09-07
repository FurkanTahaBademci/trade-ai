"""Paper portfoy API semalari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PaperPortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    strategy_version: str
    base_currency: str
    status: str
    initial_cash: float
    cash_balance: float
    realized_pnl: float
    total_fees: float
    created_at: datetime
    updated_at: datetime


class PaperPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    ticker: str
    quantity: float
    average_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    opened_at: datetime
    updated_at: datetime


class PaperTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    signal_snapshot_id: int | None
    strategy_version: str
    trade_date: date
    side: str
    quantity: float
    price: float
    gross_amount: float
    fee_amount: float
    realized_pnl: float | None
    reason: str
    created_at: datetime


class PaperPortfolioSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    snapshot_date: date
    cash_balance: float
    positions_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_return_pct: float
    position_count: int
    weights: dict
    computed_at: datetime
