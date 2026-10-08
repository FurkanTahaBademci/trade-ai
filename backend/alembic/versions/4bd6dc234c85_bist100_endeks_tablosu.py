"""BIST100 (XU100) gunluk endeks tablosu.

Revision ID: 4bd6dc234c85
Revises: d8a7e4c1b920
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4bd6dc234c85"
down_revision: str | None = "d8a7e4c1b920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_code", sa.String(16), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("index_code", "date", name="uq_index_daily_code_date"),
    )
    op.create_index("ix_index_daily_index_code", "index_daily", ["index_code"])
    op.create_index("ix_index_daily_date", "index_daily", ["date"])


def downgrade() -> None:
    op.drop_index("ix_index_daily_date", table_name="index_daily")
    op.drop_index("ix_index_daily_index_code", table_name="index_daily")
    op.drop_table("index_daily")
