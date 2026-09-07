"""LLM degerlendirme tablosu.

Revision ID: f47a1c8d6b20
Revises: d3f6a81c2e90
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f47a1c8d6b20"
down_revision: str | None = "d3f6a81c2e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_evaluation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("evaluation_key", sa.String(length=64), nullable=False),
        sa.Column("parent_evaluation_key", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("input_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ticker_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relevance_score", sa.SmallInteger(), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("impact_score", sa.SmallInteger(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=True),
        sa.Column("time_horizon", sa.String(length=16), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("requires_tier2", sa.Boolean(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_llm_evaluation_confidence",
        ),
        sa.CheckConstraint(
            "impact_score IS NULL OR impact_score BETWEEN 0 AND 100",
            name="ck_llm_evaluation_impact_score",
        ),
        sa.CheckConstraint(
            "relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100",
            name="ck_llm_evaluation_relevance_score",
        ),
        sa.CheckConstraint(
            "sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1",
            name="ck_llm_evaluation_sentiment_score",
        ),
        sa.CheckConstraint(
            "source_type IN ('news', 'kap')", name="ck_llm_evaluation_source_type"
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_llm_evaluation_status",
        ),
        sa.CheckConstraint("tier IN (1, 2)", name="ck_llm_evaluation_tier"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_key"),
    )
    op.create_index(
        "ix_llm_evaluation_parent_evaluation_key",
        "llm_evaluation",
        ["parent_evaluation_key"],
    )
    op.create_index(
        "ix_llm_evaluation_source", "llm_evaluation", ["source_type", "source_id"]
    )
    op.create_index(
        "ix_llm_evaluation_status_tier_created",
        "llm_evaluation",
        ["status", "tier", "created_at"],
    )
    op.create_index(
        "ix_llm_evaluation_ticker_codes_gin",
        "llm_evaluation",
        ["ticker_codes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_llm_evaluation_ticker_codes_gin", table_name="llm_evaluation")
    op.drop_index("ix_llm_evaluation_status_tier_created", table_name="llm_evaluation")
    op.drop_index("ix_llm_evaluation_source", table_name="llm_evaluation")
    op.drop_index("ix_llm_evaluation_parent_evaluation_key", table_name="llm_evaluation")
    op.drop_table("llm_evaluation")
