"""Temel analiz tablolari.

Revision ID: a91e5c7d3f42
Revises: f47a1c8d6b20
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a91e5c7d3f42"
down_revision: str | None = "f47a1c8d6b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_fact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("financial_group", sa.String(length=16), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("period", sa.SmallInteger(), nullable=False),
        sa.Column("item_code", sa.String(length=32), nullable=False),
        sa.Column("item_name_tr", sa.String(length=512), nullable=False),
        sa.Column("item_name_en", sa.String(length=512), nullable=True),
        sa.Column("value", sa.Numeric(precision=30, scale=4), nullable=False),
        sa.Column("raw_value", sa.String(length=128), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("period IN (3, 6, 9, 12)", name="ck_financial_fact_period"),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker",
            "financial_group",
            "exchange",
            "year",
            "period",
            "item_code",
            name="uq_financial_fact_identity",
        ),
    )
    op.create_index(
        "ix_financial_fact_ticker_period", "financial_fact", ["ticker", "year", "period"]
    )

    op.create_table(
        "fundamental_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("financial_group", sa.String(length=16), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("period", sa.SmallInteger(), nullable=False),
        sa.Column("revenue", sa.Numeric(30, 4), nullable=True),
        sa.Column("gross_profit", sa.Numeric(30, 4), nullable=True),
        sa.Column("operating_profit", sa.Numeric(30, 4), nullable=True),
        sa.Column("ebitda_proxy", sa.Numeric(30, 4), nullable=True),
        sa.Column("net_income", sa.Numeric(30, 4), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("current_assets", sa.Numeric(30, 4), nullable=True),
        sa.Column("cash", sa.Numeric(30, 4), nullable=True),
        sa.Column("current_liabilities", sa.Numeric(30, 4), nullable=True),
        sa.Column("short_term_debt", sa.Numeric(30, 4), nullable=True),
        sa.Column("long_term_debt", sa.Numeric(30, 4), nullable=True),
        sa.Column("equity", sa.Numeric(30, 4), nullable=True),
        sa.Column("revenue_yoy", sa.Numeric(14, 8), nullable=True),
        sa.Column("net_income_yoy", sa.Numeric(14, 8), nullable=True),
        sa.Column("gross_margin", sa.Numeric(14, 8), nullable=True),
        sa.Column("operating_margin", sa.Numeric(14, 8), nullable=True),
        sa.Column("net_margin", sa.Numeric(14, 8), nullable=True),
        sa.Column("current_ratio", sa.Numeric(14, 8), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(14, 8), nullable=True),
        sa.Column("cash_to_debt", sa.Numeric(14, 8), nullable=True),
        sa.Column("annualized_roe", sa.Numeric(14, 8), nullable=True),
        sa.Column("operating_cash_flow_margin", sa.Numeric(14, 8), nullable=True),
        sa.Column("free_cash_flow_margin", sa.Numeric(14, 8), nullable=True),
        sa.Column("fundamental_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_completeness", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("period IN (3, 6, 9, 12)", name="ck_fundamental_snapshot_period"),
        sa.CheckConstraint(
            "fundamental_score IS NULL OR fundamental_score BETWEEN 0 AND 100",
            name="ck_fundamental_snapshot_score",
        ),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker",
            "financial_group",
            "exchange",
            "year",
            "period",
            name="uq_fundamental_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_fundamental_snapshot_ticker_period",
        "fundamental_snapshot",
        ["ticker", "year", "period"],
    )


def downgrade() -> None:
    op.drop_index("ix_fundamental_snapshot_ticker_period", table_name="fundamental_snapshot")
    op.drop_table("fundamental_snapshot")
    op.drop_index("ix_financial_fact_ticker_period", table_name="financial_fact")
    op.drop_table("financial_fact")
