"""Analist konsensusune ortalama tavsiye yasi.

Skor motoru bayat hedef fiyatlarin guvenini dusurmek icin kullanir.

Revision ID: e1a9b3c57d40
Revises: c7d2e94f1a03
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1a9b3c57d40"
down_revision: str | None = "c7d2e94f1a03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyst_consensus", sa.Column("average_age_days", sa.Numeric(8, 2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("analyst_consensus", "average_age_days")
