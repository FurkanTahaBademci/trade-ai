"""Kalici backtest kosusu, sermaye egrisi ve islem kayitlari."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

BACKTEST_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class BacktestRun(Base):
    __tablename__ = "backtest_run"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_backtest_run_date_range"),
        CheckConstraint("initial_cash > 0", name="ck_backtest_run_initial_cash"),
        CheckConstraint(
            "status IN ('COMPLETED', 'INSUFFICIENT_DATA')", name="ck_backtest_run_status"
        ),
        Index("ix_backtest_run_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version: Mapped[str] = mapped_column(String(32))
    signal_model_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    final_equity: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    total_return_pct: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    annualized_volatility_pct: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    closed_trades: Mapped[int] = mapped_column(Integer)
    winning_trades: Mapped[int] = mapped_column(Integer)
    win_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    total_fees: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    signal_count: Mapped[int] = mapped_column(Integer)
    price_count: Mapped[int] = mapped_column(Integer)
    skipped_signal_count: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(BACKTEST_JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    points: Mapped[list["BacktestRunPoint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="BacktestRunPoint.point_date"
    )
    trades: Mapped[list["BacktestRunTrade"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="BacktestRunTrade.id"
    )


class BacktestRunPoint(Base):
    __tablename__ = "backtest_run_point"
    __table_args__ = (
        CheckConstraint("total_equity >= 0", name="ck_backtest_point_equity"),
        Index("ix_backtest_point_run_date", "run_id", "point_date", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("backtest_run.id", ondelete="CASCADE")
    )
    point_date: Mapped[date] = mapped_column(Date)
    cash: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    positions_value: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    total_equity: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    position_count: Mapped[int] = mapped_column(Integer)

    run: Mapped[BacktestRun] = relationship(back_populates="points")


class BacktestRunTrade(Base):
    __tablename__ = "backtest_run_trade"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_backtest_trade_side"),
        CheckConstraint("quantity > 0", name="ck_backtest_trade_quantity"),
        Index("ix_backtest_trade_run_date", "run_id", "execution_date"),
        Index("ix_backtest_trade_ticker_date", "ticker", "execution_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("backtest_run.id", ondelete="CASCADE")
    )
    ticker: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    signal_date: Mapped[date] = mapped_column(Date)
    execution_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)

    run: Mapped[BacktestRun] = relationship(back_populates="trades")
