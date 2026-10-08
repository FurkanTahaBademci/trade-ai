"""TCMB para politikasi kararlari ve kural tabanli piyasa etki senaryolari."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

MACRO_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class MonetaryPolicyDecision(Base):
    __tablename__ = "monetary_policy_decision"
    __table_args__ = (
        UniqueConstraint("decision_date", name="uq_monetary_policy_decision_date"),
        CheckConstraint("status IN ('PUBLISHED', 'SCHEDULED')", name="ck_policy_decision_status"),
        CheckConstraint(
            "decision_type IN ('HIKE', 'CUT', 'HOLD', 'SCHEDULED')", name="ck_policy_decision_type"
        ),
        CheckConstraint(
            "policy_rate IS NULL OR policy_rate BETWEEN 0 AND 100", name="ck_policy_rate_range"
        ),
        Index("ix_policy_decision_date", "decision_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_no: Mapped[str] = mapped_column(String(32), unique=True)
    decision_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))
    decision_type: Mapped[str] = mapped_column(String(16))
    policy_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    previous_policy_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    change_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lending_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    borrowing_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(768), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_impact: Mapped[dict] = mapped_column(MACRO_JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
