"""Analist gorusleri, konsensus ve TEFAS fon akimi modelleri."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

INSTITUTIONAL_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class AnalystRecommendation(Base):
    __tablename__ = "analyst_recommendation"
    __table_args__ = (
        UniqueConstraint("source", "source_key", name="uq_analyst_recommendation_source_key"),
        CheckConstraint(
            "recommendation_normalized IN ('BUY', 'HOLD', 'SELL', 'REVIEW')",
            name="ck_analyst_recommendation_value",
        ),
        Index("ix_analyst_recommendation_ticker_date", "ticker", "recommendation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(64))
    source_key: Mapped[str] = mapped_column(String(64))
    institution: Mapped[str] = mapped_column(String(128))
    recommendation_raw: Mapped[str] = mapped_column(String(128))
    recommendation_normalized: Mapped[str] = mapped_column(String(16))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    upside_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    recommendation_date: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(1024))
    raw_data: Mapped[dict] = mapped_column(INSTITUTIONAL_JSON_TYPE)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AnalystConsensus(Base):
    __tablename__ = "analyst_consensus"
    __table_args__ = (
        UniqueConstraint("ticker", "as_of_date", name="uq_analyst_consensus_identity"),
        CheckConstraint(
            "recommendation_score IS NULL OR recommendation_score BETWEEN 0 AND 100",
            name="ck_analyst_consensus_score",
        ),
        Index("ix_analyst_consensus_as_of", "as_of_date", "ticker"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    as_of_date: Mapped[date] = mapped_column(Date)
    institution_count: Mapped[int] = mapped_column(Integer)
    buy_count: Mapped[int] = mapped_column(Integer)
    hold_count: Mapped[int] = mapped_column(Integer)
    sell_count: Mapped[int] = mapped_column(Integer)
    review_count: Mapped[int] = mapped_column(Integer)
    average_target: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    median_target: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    minimum_target: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    maximum_target: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    implied_upside_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    target_dispersion: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    recommendation_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    average_age_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    source_breakdown: Mapped[dict] = mapped_column(INSTITUTIONAL_JSON_TYPE)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FundSnapshot(Base):
    __tablename__ = "fund_snapshot"
    __table_args__ = (
        UniqueConstraint("fund_kind", "fund_code", "date", name="uq_fund_snapshot_identity"),
        Index("ix_fund_snapshot_date_kind", "date", "fund_kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_kind: Mapped[str] = mapped_column(String(8))
    fund_code: Mapped[str] = mapped_column(String(32))
    date: Mapped[date] = mapped_column(Date)
    fund_name: Mapped[str] = mapped_column(String(512))
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    investor_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    portfolio_size: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    exchange_bulletin_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    stock_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    foreign_stock_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    estimated_net_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    estimated_stock_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    raw_info: Mapped[dict] = mapped_column(INSTITUTIONAL_JSON_TYPE)
    raw_allocation: Mapped[dict | None] = mapped_column(INSTITUTIONAL_JSON_TYPE, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FundFlowAggregate(Base):
    __tablename__ = "fund_flow_aggregate"
    __table_args__ = (
        UniqueConstraint("fund_kind", "date", name="uq_fund_flow_aggregate_identity"),
        Index("ix_fund_flow_aggregate_date", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_kind: Mapped[str] = mapped_column(String(8))
    date: Mapped[date] = mapped_column(Date)
    fund_count: Mapped[int] = mapped_column(Integer)
    flow_observation_count: Mapped[int] = mapped_column(Integer)
    total_aum: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    total_net_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    total_stock_exposure: Mapped[Decimal] = mapped_column(Numeric(30, 4))
    estimated_stock_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4), nullable=True)
    positive_flow_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
