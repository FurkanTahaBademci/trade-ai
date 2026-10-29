"""Canli emir gondermeyen paper portfoy, pozisyon, islem, emir ve performans modelleri.

`owner_id` bos olan portfoy sistemin herkese acik model portfoyudur; dolu olanlar
kullanicilarindir. Kullanici portfoyu ya bilesik sinyali kendi ayarlariyla
izler (STRATEGY) ya da kullanicinin verdigi emirlerle islem yapar (MANUAL).
"""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

PAPER_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
# SQLite (testler) yalniz INTEGER PRIMARY KEY'i otomatik artirir.
PAPER_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")
PORTFOLIO_KINDS = ("STRATEGY", "MANUAL")
ORDER_STATUSES = ("PENDING", "FILLED", "REJECTED", "CANCELLED")


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolio"
    __table_args__ = (
        CheckConstraint("initial_cash > 0", name="ck_paper_portfolio_initial_cash"),
        CheckConstraint("cash_balance >= 0", name="ck_paper_portfolio_cash_balance"),
        CheckConstraint("status IN ('ACTIVE', 'PAUSED')", name="ck_paper_portfolio_status"),
        CheckConstraint("kind IN ('STRATEGY', 'MANUAL')", name="ck_paper_portfolio_kind"),
        # Model portfoy adiyla, kullanici portfoyleri sahibi icinde tekildir.
        Index(
            "uq_paper_portfolio_system_name",
            "name",
            unique=True,
            postgresql_where=text("owner_id IS NULL"),
            sqlite_where=text("owner_id IS NULL"),
        ),
        Index(
            "uq_paper_portfolio_owner_name",
            "owner_id",
            "name",
            unique=True,
            postgresql_where=text("owner_id IS NOT NULL"),
            sqlite_where=text("owner_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(PAPER_ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[int | None] = mapped_column(
        PAPER_ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="STRATEGY")
    # STRATEGY portfoyunun ayarlari (app/paper/strategy.py StrategyConfig); bos =
    # model portfoy gibi kod varsayilanlari + /sistem risk ayarlari.
    config: Mapped[dict | None] = mapped_column(PAPER_JSON_TYPE, nullable=True)
    # Ilk islem gunu; olusturulmadan onceki kapanislar oynatilmaz.
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    strategy_version: Mapped[str] = mapped_column(String(32))
    base_currency: Mapped[str] = mapped_column(String(8), default="TRY")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 4), default=0)
    total_fees: Mapped[Decimal] = mapped_column(Numeric(30, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    positions: Mapped[list["PaperPosition"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class PaperPosition(Base):
    __tablename__ = "paper_position"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", name="uq_paper_position_identity"),
        CheckConstraint("quantity > 0", name="ck_paper_position_quantity"),
        CheckConstraint("average_cost > 0", name="ck_paper_position_average_cost"),
        Index("ix_paper_position_portfolio", "portfolio_id", "ticker"),
    )

    id: Mapped[int] = mapped_column(PAPER_ID_TYPE, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("paper_portfolio.id", ondelete="CASCADE")
    )
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    last_price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    market_value: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    high_water_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="positions")


class PaperTrade(Base):
    __tablename__ = "paper_trade"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_paper_trade_side"),
        CheckConstraint("quantity > 0", name="ck_paper_trade_quantity"),
        CheckConstraint("price > 0", name="ck_paper_trade_price"),
        CheckConstraint("gross_amount > 0", name="ck_paper_trade_gross"),
        Index("ix_paper_trade_portfolio_date", "portfolio_id", "trade_date"),
        Index("ix_paper_trade_ticker_date", "ticker", "trade_date"),
    )

    id: Mapped[int] = mapped_column(PAPER_ID_TYPE, primary_key=True, autoincrement=True)
    execution_key: Mapped[str] = mapped_column(String(64), unique=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("paper_portfolio.id", ondelete="CASCADE")
    )
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    signal_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("composite_signal_snapshot.id", ondelete="SET NULL"),
        nullable=True,
    )
    strategy_version: Mapped[str] = mapped_column(String(32))
    trade_date: Mapped[date] = mapped_column(Date)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    reason: Mapped[str] = mapped_column(String(256))
    exit_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperPortfolioSnapshot(Base):
    __tablename__ = "paper_portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "snapshot_date", name="uq_paper_portfolio_snapshot_identity"
        ),
        CheckConstraint("total_equity >= 0", name="ck_paper_snapshot_equity"),
        Index("ix_paper_snapshot_portfolio_date", "portfolio_id", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(PAPER_ID_TYPE, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("paper_portfolio.id", ondelete="CASCADE")
    )
    snapshot_date: Mapped[date] = mapped_column(Date)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    positions_value: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    total_equity: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    total_return_pct: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    position_count: Mapped[int] = mapped_column(Integer)
    weights: Mapped[dict] = mapped_column(PAPER_JSON_TYPE)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaperOrder(Base):
    """Manuel portfoyde kullanicinin verdigi sanal emir.

    Emir, `not_before` gunu ve sonrasindaki ilk uygun islem gununun kapanis
    fiyatindan (kayma ve komisyonla) gerceklesir; kapanisi bilinen gun icin
    verilen emir o kapanistan islem goremez.
    """

    __tablename__ = "paper_order"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_paper_order_side"),
        CheckConstraint(
            "status IN ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED')",
            name="ck_paper_order_status",
        ),
        CheckConstraint("quantity IS NOT NULL OR amount IS NOT NULL", name="ck_paper_order_size"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_paper_order_quantity"),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_paper_order_amount"),
        UniqueConstraint("portfolio_id", "client_order_id", name="uq_paper_order_client_id"),
        Index("ix_paper_order_portfolio_status", "portfolio_id", "status"),
    )

    id: Mapped[int] = mapped_column(PAPER_ID_TYPE, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        PAPER_ID_TYPE, ForeignKey("paper_portfolio.id", ondelete="CASCADE")
    )
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    side: Mapped[str] = mapped_column(String(8))
    # Adet (tam sayi) ya da TL tutar; satista adet zorunludur.
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    not_before: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trade_id: Mapped[int | None] = mapped_column(
        PAPER_ID_TYPE, ForeignKey("paper_trade.id", ondelete="SET NULL"), nullable=True
    )
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    filled_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
