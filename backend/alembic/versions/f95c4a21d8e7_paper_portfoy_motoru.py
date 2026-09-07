"""Paper portfoy motoru tablolari.

Revision ID: f95c4a21d8e7
Revises: e84b2b3d91f0
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f95c4a21d8e7"
down_revision: str | None = "e84b2b3d91f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_portfolio",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("initial_cash", sa.Numeric(30, 4), nullable=False),
        sa.Column("cash_balance", sa.Numeric(30, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_fees", sa.Numeric(30, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("initial_cash > 0", name="ck_paper_portfolio_initial_cash"),
        sa.CheckConstraint("cash_balance >= 0", name="ck_paper_portfolio_cash_balance"),
        sa.CheckConstraint("status IN ('ACTIVE', 'PAUSED')", name="ck_paper_portfolio_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "paper_position",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(24, 8), nullable=False),
        sa.Column("last_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("market_value", sa.Numeric(30, 4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(30, 4), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_paper_position_quantity"),
        sa.CheckConstraint("average_cost > 0", name="ck_paper_position_average_cost"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "ticker", name="uq_paper_position_identity"),
    )
    op.create_index("ix_paper_position_portfolio", "paper_position", ["portfolio_id", "ticker"])
    op.create_table(
        "paper_trade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("execution_key", sa.String(64), nullable=False),
        sa.Column("portfolio_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("signal_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("gross_amount", sa.Numeric(30, 4), nullable=False),
        sa.Column("fee_amount", sa.Numeric(30, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(30, 4), nullable=True),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_paper_trade_side"),
        sa.CheckConstraint("quantity > 0", name="ck_paper_trade_quantity"),
        sa.CheckConstraint("price > 0", name="ck_paper_trade_price"),
        sa.CheckConstraint("gross_amount > 0", name="ck_paper_trade_gross"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_snapshot_id"], ["composite_signal_snapshot.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticker"], ["instrument.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_key"),
    )
    op.create_index("ix_paper_trade_portfolio_date", "paper_trade", ["portfolio_id", "trade_date"])
    op.create_index("ix_paper_trade_ticker_date", "paper_trade", ["ticker", "trade_date"])
    op.create_table(
        "paper_portfolio_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("cash_balance", sa.Numeric(30, 4), nullable=False),
        sa.Column("positions_value", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_equity", sa.Numeric(30, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(30, 4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_return_pct", sa.Numeric(14, 8), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total_equity >= 0", name="ck_paper_snapshot_equity"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_paper_portfolio_snapshot_identity"),
    )
    op.create_index("ix_paper_snapshot_portfolio_date", "paper_portfolio_snapshot", ["portfolio_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_index("ix_paper_snapshot_portfolio_date", table_name="paper_portfolio_snapshot")
    op.drop_table("paper_portfolio_snapshot")
    op.drop_index("ix_paper_trade_ticker_date", table_name="paper_trade")
    op.drop_index("ix_paper_trade_portfolio_date", table_name="paper_trade")
    op.drop_table("paper_trade")
    op.drop_index("ix_paper_position_portfolio", table_name="paper_position")
    op.drop_table("paper_position")
    op.drop_table("paper_portfolio")
