"""Surumlu bilesik skor ve teknik sinyal snapshot'lari."""

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
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SIGNAL_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class CompositeSignalSnapshot(Base):
    """Bir ticker icin belirli gundeki aciklanabilir bilesik skor.

    `model_version` agirlik/esik degisikliginde eski sonuclari bozmadan yeni
    seriyi yan yana tutar. Bilesen, etkin agirlik ve kaynak kimlikleri JSONB
    alanlarinda saklandigi icin her skor geriye donuk denetlenebilir.
    """

    __tablename__ = "composite_signal_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "as_of_date", "model_version", name="uq_composite_signal_identity"
        ),
        CheckConstraint(
            "composite_score BETWEEN 0 AND 100", name="ck_composite_signal_score"
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_composite_signal_confidence"),
        CheckConstraint("coverage_count BETWEEN 1 AND 4", name="ck_composite_signal_coverage"),
        CheckConstraint(
            "signal_label IN ('VERY_POSITIVE', 'POSITIVE', 'NEUTRAL', "
            "'NEGATIVE', 'VERY_NEGATIVE')",
            name="ck_composite_signal_label",
        ),
        Index("ix_composite_signal_date_score", "as_of_date", "composite_score"),
        Index("ix_composite_signal_ticker_date", "ticker", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(16), ForeignKey("instrument.ticker", ondelete="CASCADE")
    )
    as_of_date: Mapped[date] = mapped_column(Date)
    model_version: Mapped[str] = mapped_column(String(16))
    composite_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    signal_label: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    coverage_count: Mapped[int] = mapped_column(SmallInteger)
    component_scores: Mapped[dict] = mapped_column(SIGNAL_JSON_TYPE)
    component_weights: Mapped[dict] = mapped_column(SIGNAL_JSON_TYPE)
    evidence: Mapped[dict] = mapped_column(SIGNAL_JSON_TYPE)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
