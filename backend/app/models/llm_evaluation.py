"""Haber ve KAP girdileri icin surumlu LLM degerlendirmeleri.

Polymorphic kaynak (`news`/`kap`) bilincli olarak fiziksel foreign key
kullanmaz. `source_type + source_id` girdiyi isaret eder; `content_hash`,
prompt/model/tier ile birlikte ayni girdi surumunun tekrar ucretli cagrilmasini
engelleyen deterministik `evaluation_key` degerine katilir.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

LLM_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class LlmEvaluation(Base):
    __tablename__ = "llm_evaluation"
    __table_args__ = (
        CheckConstraint("source_type IN ('news', 'kap')", name="ck_llm_evaluation_source_type"),
        CheckConstraint("tier IN (1, 2)", name="ck_llm_evaluation_tier"),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_llm_evaluation_status",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100",
            name="ck_llm_evaluation_relevance_score",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1",
            name="ck_llm_evaluation_sentiment_score",
        ),
        CheckConstraint(
            "impact_score IS NULL OR impact_score BETWEEN 0 AND 100",
            name="ck_llm_evaluation_impact_score",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_llm_evaluation_confidence",
        ),
        Index("ix_llm_evaluation_source", "source_type", "source_id"),
        Index("ix_llm_evaluation_status_tier_created", "status", "tier", "created_at"),
        Index("ix_llm_evaluation_ticker_codes_gin", "ticker_codes", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_key: Mapped[str] = mapped_column(String(64), unique=True)
    parent_evaluation_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    tier: Mapped[int] = mapped_column(SmallInteger)
    provider: Mapped[str] = mapped_column(String(32), default="google")
    model: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)

    input_document: Mapped[dict] = mapped_column(LLM_JSON_TYPE)
    ticker_codes: Mapped[list[str]] = mapped_column(LLM_JSON_TYPE, default=list)
    relevance_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    impact_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_tier2: Mapped[bool] = mapped_column(Boolean, default=False)

    result: Mapped[dict | None] = mapped_column(LLM_JSON_TYPE, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<LlmEvaluation {self.source_type}:{self.source_id} "
            f"tier={self.tier} status={self.status}>"
        )
