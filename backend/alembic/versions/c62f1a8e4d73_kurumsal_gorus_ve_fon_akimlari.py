"""Kurumsal gorus ve fon akimi tablolari.

Revision ID: c62f1a8e4d73
Revises: a91e5c7d3f42
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c62f1a8e4d73"
down_revision: str | None = "a91e5c7d3f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyst_recommendation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("institution", sa.String(128), nullable=False),
        sa.Column("recommendation_raw", sa.String(128), nullable=False),
        sa.Column("recommendation_normalized", sa.String(16), nullable=False),
        sa.Column("target_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("reference_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("upside_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "recommendation_normalized IN ('BUY', 'HOLD', 'SELL', 'REVIEW')",
            name="ck_analyst_recommendation_value",
        ),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_key", name="uq_analyst_recommendation_source_key"),
    )
    op.create_index(
        "ix_analyst_recommendation_ticker_date",
        "analyst_recommendation",
        ["ticker", "recommendation_date"],
    )

    op.create_table(
        "analyst_consensus",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("institution_count", sa.Integer(), nullable=False),
        sa.Column("buy_count", sa.Integer(), nullable=False),
        sa.Column("hold_count", sa.Integer(), nullable=False),
        sa.Column("sell_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("average_target", sa.Numeric(20, 4), nullable=True),
        sa.Column("median_target", sa.Numeric(20, 4), nullable=True),
        sa.Column("minimum_target", sa.Numeric(20, 4), nullable=True),
        sa.Column("maximum_target", sa.Numeric(20, 4), nullable=True),
        sa.Column("market_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("implied_upside_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("target_dispersion", sa.Numeric(12, 8), nullable=True),
        sa.Column("recommendation_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("source_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "recommendation_score IS NULL OR recommendation_score BETWEEN 0 AND 100",
            name="ck_analyst_consensus_score",
        ),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "as_of_date", name="uq_analyst_consensus_identity"),
    )
    op.create_index("ix_analyst_consensus_as_of", "analyst_consensus", ["as_of_date", "ticker"])

    op.create_table(
        "fund_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_kind", sa.String(8), nullable=False),
        sa.Column("fund_code", sa.String(32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fund_name", sa.String(512), nullable=False),
        sa.Column("price", sa.Numeric(24, 10), nullable=True),
        sa.Column("shares_outstanding", sa.Numeric(30, 4), nullable=True),
        sa.Column("investor_count", sa.BigInteger(), nullable=True),
        sa.Column("portfolio_size", sa.Numeric(30, 4), nullable=True),
        sa.Column("exchange_bulletin_price", sa.Numeric(24, 10), nullable=True),
        sa.Column("stock_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("foreign_stock_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("estimated_net_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("estimated_stock_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("raw_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_allocation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_kind", "fund_code", "date", name="uq_fund_snapshot_identity"),
    )
    op.create_index("ix_fund_snapshot_date_kind", "fund_snapshot", ["date", "fund_kind"])

    op.create_table(
        "fund_flow_aggregate",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_kind", sa.String(8), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fund_count", sa.Integer(), nullable=False),
        sa.Column("flow_observation_count", sa.Integer(), nullable=False),
        sa.Column("total_aum", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_net_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("total_stock_exposure", sa.Numeric(30, 4), nullable=False),
        sa.Column("estimated_stock_flow", sa.Numeric(30, 4), nullable=True),
        sa.Column("positive_flow_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_kind", "date", name="uq_fund_flow_aggregate_identity"),
    )
    op.create_index("ix_fund_flow_aggregate_date", "fund_flow_aggregate", ["date"])


def downgrade() -> None:
    op.drop_index("ix_fund_flow_aggregate_date", table_name="fund_flow_aggregate")
    op.drop_table("fund_flow_aggregate")
    op.drop_index("ix_fund_snapshot_date_kind", table_name="fund_snapshot")
    op.drop_table("fund_snapshot")
    op.drop_index("ix_analyst_consensus_as_of", table_name="analyst_consensus")
    op.drop_table("analyst_consensus")
    op.drop_index("ix_analyst_recommendation_ticker_date", table_name="analyst_recommendation")
    op.drop_table("analyst_recommendation")
