"""Backtest calistirma ve sonuc API semalari."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ComponentName = Literal["llm", "fundamental", "analyst", "momentum"]


class BacktestCreate(BaseModel):
    start_date: date
    end_date: date
    initial_cash: float = Field(default=1_000_000, gt=0, le=1_000_000_000)
    entry_score: float = Field(default=75, ge=0, le=100)
    exit_score: float = Field(default=55, ge=0, le=100)
    min_confidence: float = Field(default=0.25, ge=0, le=1)
    min_coverage: int = Field(default=2, ge=1, le=4)
    max_positions: int = Field(default=10, ge=1, le=100)
    max_position_weight: float = Field(default=0.10, gt=0, le=1)
    fee_rate: float = Field(default=0.001, ge=0, le=0.05)
    slippage_rate: float = Field(default=0.0005, ge=0, le=0.05)
    # Varsayilanlar paper portfoyle ayni: %15 zarar-kes, gunde en fazla 3 yeni pozisyon.
    stop_loss_pct: float = Field(default=15, ge=0, lt=100)
    max_new_entries_per_day: int = Field(default=3, ge=0, le=100)
    # Gercekci yurutme: tavan/taban esigi (BIST gunluk limiti %10), son 20 gunun
    # ortalama TL hacmi alt siniri ve istege bagli XU100 rejim filtresi (0 = kapali).
    price_limit_pct: float = Field(default=9.5, ge=0, lt=100)
    min_avg_volume: float = Field(default=20_000_000, ge=0, le=100_000_000_000)
    regime_ma_days: int = Field(default=0, ge=0, le=250)
    max_volatility_pct: float = Field(default=0, ge=0, le=50)
    # "basket": her `rebalance_days` islem gununde skoru en yuksek `basket_size`
    # likit hisseyi esit agirlikla tutar; giris/cikis skoru, zarar-kes ve pozisyon
    # sayisi/agirligi bu stratejide kullanilmaz.
    strategy: Literal["threshold", "basket"] = "threshold"
    basket_size: int = Field(default=20, ge=1, le=100)
    basket_keep: int = Field(default=40, ge=1, le=200)
    rebalance_days: int = Field(default=10, ge=1, le=60)
    # Agirlik simulasyonu: verilirse skor, saklanan bilesen skorlarindan bu
    # agirliklarla yeniden hesaplanir (bos = canli modelin skoru).
    component_weights: dict[ComponentName, float] | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "BacktestCreate":
        if self.basket_keep < self.basket_size:
            raise ValueError("basket_keep basket_size'dan kucuk olamaz")
        if self.component_weights is not None:
            if any(not (0 <= value <= 1) for value in self.component_weights.values()):
                raise ValueError("component_weights degerleri 0 ile 1 arasinda olmali")
            if sum(self.component_weights.values()) <= 0:
                raise ValueError("component_weights en az bir pozitif agirlik icermeli")
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
    robustness: dict | None = None
    created_at: datetime


class BacktestRunDetailOut(BacktestRunSummaryOut):
    points: list[BacktestPointOut]
    trades: list[BacktestTradeOut]
