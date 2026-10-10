"""TCMB EVDS makro seri gozlemleri (kur, TUFE).

Revision ID: c1e6a8d27f49
Revises: b9d4f1a6c382
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1e6a8d27f49"
down_revision: str | None = "b9d4f1a6c382"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "macro_series_point",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("series_code", sa.String(32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("series_code", "date", name="uq_macro_series_point_identity"),
    )
    op.create_index(
        "ix_macro_series_point_series_date", "macro_series_point", ["series_code", "date"]
    )


def downgrade() -> None:
    op.drop_index("ix_macro_series_point_series_date", table_name="macro_series_point")
    op.drop_table("macro_series_point")
