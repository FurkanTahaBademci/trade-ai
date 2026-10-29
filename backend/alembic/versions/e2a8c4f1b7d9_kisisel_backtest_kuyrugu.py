"""Kisisel backtest: kosu sahibi, kuyruk durumlari ve bos birakilabilen sonuc kolonlari.

Kosu artik API isteginde degil worker'da hesaplanir: once QUEUED yazilir,
RUNNING olur, COMPLETED / INSUFFICIENT_DATA / FAILED ile biter. Mevcut kosular
sistem (yonetici) kosusu olarak kalir.

Revision ID: e2a8c4f1b7d9
Revises: d7e1a4b9c352
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2a8c4f1b7d9"
down_revision: str | None = "d7e1a4b9c352"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULT_COLUMNS = (
    ("final_equity", sa.Numeric(30, 4)),
    ("total_return_pct", sa.Numeric(14, 8)),
    ("max_drawdown_pct", sa.Numeric(14, 8)),
    ("closed_trades", sa.Integer()),
    ("winning_trades", sa.Integer()),
    ("total_fees", sa.Numeric(30, 4)),
    ("signal_count", sa.Integer()),
    ("price_count", sa.Integer()),
    ("skipped_signal_count", sa.Integer()),
)


def upgrade() -> None:
    op.add_column(
        "backtest_run",
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "backtest_run", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "backtest_run", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("backtest_run", sa.Column("error", sa.String(500), nullable=True))
    for name, type_ in RESULT_COLUMNS:
        op.alter_column("backtest_run", name, existing_type=type_, nullable=True)
    op.drop_constraint("ck_backtest_run_status", "backtest_run", type_="check")
    op.create_check_constraint(
        "ck_backtest_run_status",
        "backtest_run",
        "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'INSUFFICIENT_DATA', 'FAILED')",
    )
    op.create_index("ix_backtest_run_owner", "backtest_run", ["owner_id", "id"])


def downgrade() -> None:
    # Eski sema yalniz tamamlanmis sistem kosularini tasiyabilir.
    op.execute(
        "DELETE FROM backtest_run "
        "WHERE owner_id IS NOT NULL OR status NOT IN ('COMPLETED', 'INSUFFICIENT_DATA')"
    )
    op.drop_index("ix_backtest_run_owner", table_name="backtest_run")
    op.drop_constraint("ck_backtest_run_status", "backtest_run", type_="check")
    op.create_check_constraint(
        "ck_backtest_run_status", "backtest_run", "status IN ('COMPLETED', 'INSUFFICIENT_DATA')"
    )
    for name, type_ in RESULT_COLUMNS:
        op.alter_column("backtest_run", name, existing_type=type_, nullable=False)
    for column in ("error", "finished_at", "started_at", "owner_id"):
        op.drop_column("backtest_run", column)
