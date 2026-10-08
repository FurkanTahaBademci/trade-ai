"""Finansal tablo gercekleri ve deterministik temel analiz snapshot'lari."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

FUNDAMENTAL_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class FinancialFact(Base):
    __tablename__ = "financial_fact"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "financial_group",
            "exchange",
            "year",
            "period",
            "item_code",
            name="uq_financial_fact_identity",
        ),
        CheckConstraint("period IN (3, 6, 9, 12)", name="ck_financial_fact_period"),
        Index("ix_financial_fact_ticker_period", "ticker", "year", "period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    financial_group: Mapped[str] = mapped_column(String(16))
    exchange: Mapped[str] = mapped_column(String(8), default="TRY")
    year: Mapped[int] = mapped_column(SmallInteger)
    period: Mapped[int] = mapped_column(SmallInteger)
    item_code: Mapped[str] = mapped_column(String(32))
    item_name_tr: Mapped[str] = mapped_column(String(512))
    item_name_en: Mapped[str | None] = mapped_column(String(512), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    raw_value: Mapped[str] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "financial_group",
            "exchange",
            "year",
            "period",
            name="uq_fundamental_snapshot_identity",
        ),
        CheckConstraint("period IN (3, 6, 9, 12)", name="ck_fundamental_snapshot_period"),
        CheckConstraint(
            "fundamental_score IS NULL OR fundamental_score BETWEEN 0 AND 100",
            name="ck_fundamental_snapshot_score",
        ),
        Index("ix_fundamental_snapshot_ticker_period", "ticker", "year", "period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    financial_group: Mapped[str] = mapped_column(String(16))
    exchange: Mapped[str] = mapped_column(String(8), default="TRY")
    year: Mapped[int] = mapped_column(SmallInteger)
    period: Mapped[int] = mapped_column(SmallInteger)

    revenue: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    operating_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    ebitda_proxy: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    current_assets: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    cash: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    current_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    short_term_debt: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    long_term_debt: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    equity: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)

    revenue_yoy: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    net_income_yoy: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    cash_to_debt: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    annualized_roe: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    operating_cash_flow_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 8), nullable=True
    )
    free_cash_flow_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)

    fundamental_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_components: Mapped[dict] = mapped_column(FUNDAMENTAL_JSON_TYPE, default=dict)
    data_completeness: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
