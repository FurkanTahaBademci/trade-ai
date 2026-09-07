"""TCMB para politikasi kararlari.

Revision ID: b7d4e9a2c610
Revises: f95c4a21d8e7
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7d4e9a2c610"
down_revision: str | None = "f95c4a21d8e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monetary_policy_decision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("decision_no", sa.String(32), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("decision_type", sa.String(16), nullable=False),
        sa.Column("policy_rate", sa.Numeric(7, 3), nullable=True),
        sa.Column("previous_policy_rate", sa.Numeric(7, 3), nullable=True),
        sa.Column("change_bps", sa.Integer(), nullable=True),
        sa.Column("lending_rate", sa.Numeric(7, 3), nullable=True),
        sa.Column("borrowing_rate", sa.Numeric(7, 3), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(768), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("market_impact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('PUBLISHED', 'SCHEDULED')", name="ck_policy_decision_status"),
        sa.CheckConstraint("decision_type IN ('HIKE', 'CUT', 'HOLD', 'SCHEDULED')", name="ck_policy_decision_type"),
        sa.CheckConstraint("policy_rate IS NULL OR policy_rate BETWEEN 0 AND 100", name="ck_policy_rate_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_date", name="uq_monetary_policy_decision_date"),
        sa.UniqueConstraint("decision_no"),
    )
    op.create_index("ix_policy_decision_date", "monetary_policy_decision", ["decision_date"])


def downgrade() -> None:
    op.drop_index("ix_policy_decision_date", table_name="monetary_policy_decision")
    op.drop_table("monetary_policy_decision")
