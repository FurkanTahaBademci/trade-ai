"""Sunucu tarafi izleme listesi.

Revision ID: b9d4f1a6c382
Revises: a3c5e7f92b18
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d4f1a6c382"
down_revision: str | None = "a3c5e7f92b18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlist_item",
        sa.Column("ticker", sa.String(16), primary_key=True),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("watchlist_item")
