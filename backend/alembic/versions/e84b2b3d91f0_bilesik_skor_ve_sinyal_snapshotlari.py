"""Bilesik skor ve sinyal snapshot tablosu.

Revision ID: e84b2b3d91f0
Revises: c62f1a8e4d73
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e84b2b3d91f0"
down_revision: str | None = "c62f1a8e4d73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "composite_signal_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("model_version", sa.String(16), nullable=False),
        sa.Column("composite_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("signal_label", sa.String(24), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("coverage_count", sa.SmallInteger(), nullable=False),
        sa.Column("component_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("component_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "composite_score BETWEEN 0 AND 100", name="ck_composite_signal_score"
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_composite_signal_confidence"
        ),
        sa.CheckConstraint(
            "coverage_count BETWEEN 1 AND 4", name="ck_composite_signal_coverage"
        ),
        sa.CheckConstraint(
            "signal_label IN ('VERY_POSITIVE', 'POSITIVE', 'NEUTRAL', "
            "'NEGATIVE', 'VERY_NEGATIVE')",
            name="ck_composite_signal_label",
        ),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "as_of_date", "model_version", name="uq_composite_signal_identity"
        ),
    )
    op.create_index(
        "ix_composite_signal_date_score",
        "composite_signal_snapshot",
        ["as_of_date", "composite_score"],
    )
    op.create_index(
        "ix_composite_signal_ticker_date",
        "composite_signal_snapshot",
        ["ticker", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_composite_signal_ticker_date", table_name="composite_signal_snapshot")
    op.drop_index("ix_composite_signal_date_score", table_name="composite_signal_snapshot")
    op.drop_table("composite_signal_snapshot")
