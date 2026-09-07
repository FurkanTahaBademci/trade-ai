"""Backtest calistirma ve sonuc API semalari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BacktestCreate(BaseModel):
    start_date: date
    end_date: date
    initial_cash: float = Field(default=1_000_000, gt=0, le=1_000_000_000)
    entry_score: float = Field(default=75, ge=0, le=100)
    exit_score: float = Field(default=40, ge=0, le=100)
    min_confidence: float = Field(default=0.25, ge=0, le=1)
    min_coverage: int = Field(default=2, ge=1, le=4)
    max_positions: int = Field(default=10, ge=1, le=100)
    max_position_weight: float = Field(default=0.10, gt=0, le=1)
    fee_rate: float = Field(default=0.001, ge=0, le=0.05)
    slippage_rate: float = Field(default=0.0005, ge=0, le=0.05)

    @model_validator(mode="after")
    def validate_ranges(self) -> "BacktestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date start_date'den once olamaz")
        if (self.end_date - self.start_date).days > 3650:
            raise ValueError("tarih araligi en fazla 10 yil olabilir")
        if self.exit_score >= self.entry_score:
            raise ValueError("exit_score entry_score'dan kucuk olmali")
        if self.max_positions * self.max_position_weight > 1:
            raise ValueError("pozisyon agirliklari toplam limiti asiyor")
        return self


class BacktestPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    point_date: date
    cash: float
    positions_value: float
    total_equity: float
    position_count: int


class BacktestTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    side: str
    signal_date: date
    execution_date: date
    quantity: float
    price: float
    gross_amount: float
    fee_amount: float
    realized_pnl: float | None


class BacktestRunSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_version: str
    signal_model_version: str
    status: str
    start_date: date
    end_date: date
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    annualized_volatility_pct: float | None
    sharpe_ratio: float | None
    closed_trades: int
    winning_trades: int
    win_rate_pct: float | None
    total_fees: float
    signal_count: int
    price_count: int
    skipped_signal_count: int
    config: dict
    created_at: datetime


class BacktestRunDetailOut(BacktestRunSummaryOut):
    points: list[BacktestPointOut]
    trades: list[BacktestTradeOut]
