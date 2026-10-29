"""Paper portfoy API semalari."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.paper.strategy import StrategyConfig, TemplateName


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
    high_water_price: float | None = None
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
    exit_reason: str | None = None
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


class PaperRiskRulesOut(BaseModel):
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float
    max_position_weight_pct: float
    max_sector_weight_pct: float
    rebalance_enabled: bool


class PaperSectorWeightOut(BaseModel):
    sector: str
    value: float
    weight_pct: float


class PaperRiskOut(BaseModel):
    portfolio_id: int
    observations: int
    max_drawdown_pct: float
    volatility_pct: float | None
    top_position_ticker: str | None
    top_position_weight_pct: float
    cash_weight_pct: float
    sector_allocation: list[PaperSectorWeightOut]
    rules: PaperRiskRulesOut


# --- Kullanici portfoyleri (/api/me/portfolios) ---------------------------------

PortfolioKind = Literal["STRATEGY", "MANUAL"]


class MyPortfolioOut(PaperPortfolioOut):
    kind: PortfolioKind
    config: StrategyConfig | None = None
    started_on: date | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None


class MyPortfolioSummaryOut(MyPortfolioOut):
    """Liste karti: son gun sonu degerlemesi ve bekleyen emir sayisi."""

    total_equity: float
    total_return_pct: float
    position_count: int
    snapshot_date: date | None = None
    pending_orders: int = 0


class MyPortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: PortfolioKind = "STRATEGY"
    initial_cash: float = Field(default=1_000_000, ge=10_000, le=10_000_000)
    # STRATEGY icin: hazir sablon ya da tam ayar (ikisi birden verilirse ayar kazanir).
    template: TemplateName | None = None
    config: StrategyConfig | None = None


class MyPortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    status: Literal["ACTIVE", "PAUSED"] | None = None
    config: StrategyConfig | None = None


class StrategyTemplateOut(BaseModel):
    key: str
    label: str
    description: str
    config: StrategyConfig


class PaperOrderCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    side: Literal["BUY", "SELL"]
    # Tam adet; alimda adet yerine TL tutar da verilebilir.
    quantity: int | None = Field(default=None, ge=1, le=100_000_000)
    amount: float | None = Field(default=None, ge=1_000, le=100_000_000)
    client_order_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_size(self) -> "PaperOrderCreate":
        if (self.quantity is None) == (self.amount is None):
            raise ValueError("Adet ya da tutardan yalnız birini gir.")
        if self.side == "SELL" and self.quantity is None:
            raise ValueError("Satış emrinde adet girilmeli.")
        return self


class PaperOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    ticker: str
    side: str
    quantity: float | None
    amount: float | None
    status: str
    not_before: date
    note: str | None
    fill_price: float | None
    filled_quantity: float | None
    filled_at: datetime | None
    created_at: datetime
