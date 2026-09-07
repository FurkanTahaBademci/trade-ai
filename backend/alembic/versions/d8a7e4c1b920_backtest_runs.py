"""Kalici backtest kosulari.

Revision ID: d8a7e4c1b920
Revises: c4e8a2b1d730
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d8a7e4c1b920"
down_revision: str | None = "c4e8a2b1d730"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("signal_model_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_cash", sa.Numeric(30, 4), nullable=False),
        sa.Column("final_equity", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_return_pct", sa.Numeric(14, 8), nullable=False),
        sa.Column("max_drawdown_pct", sa.Numeric(14, 8), nullable=False),
        sa.Column("annualized_volatility_pct", sa.Numeric(14, 8), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(14, 8), nullable=True),
        sa.Column("closed_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate_pct", sa.Numeric(14, 8), nullable=True),
        sa.Column("total_fees", sa.Numeric(30, 4), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("price_count", sa.Integer(), nullable=False),
        sa.Column("skipped_signal_count", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_backtest_run_date_range"),
        sa.CheckConstraint("initial_cash > 0", name="ck_backtest_run_initial_cash"),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'INSUFFICIENT_DATA')", name="ck_backtest_run_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_run_created_at", "backtest_run", ["created_at"])
    op.create_table(
        "backtest_run_point",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("point_date", sa.Date(), nullable=False),
        sa.Column("cash", sa.Numeric(30, 4), nullable=False),
        sa.Column("positions_value", sa.Numeric(30, 4), nullable=False),
        sa.Column("total_equity", sa.Numeric(30, 4), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("total_equity >= 0", name="ck_backtest_point_equity"),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_point_run_date", "backtest_run_point", ["run_id", "point_date"], unique=True
    )
    op.create_table(
        "backtest_run_trade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("execution_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("gross_amount", sa.Numeric(30, 4), nullable=False),
        sa.Column("fee_amount", sa.Numeric(30, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(30, 4), nullable=True),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_backtest_trade_side"),
        sa.CheckConstraint("quantity > 0", name="ck_backtest_trade_quantity"),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_trade_run_date", "backtest_run_trade", ["run_id", "execution_date"]
    )
    op.create_index(
        "ix_backtest_trade_ticker_date", "backtest_run_trade", ["ticker", "execution_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_trade_ticker_date", table_name="backtest_run_trade")
    op.drop_index("ix_backtest_trade_run_date", table_name="backtest_run_trade")
    op.drop_table("backtest_run_trade")
    op.drop_index("ix_backtest_point_run_date", table_name="backtest_run_point")
    op.drop_table("backtest_run_point")
    op.drop_index("ix_backtest_run_created_at", table_name="backtest_run")
    op.drop_table("backtest_run")
