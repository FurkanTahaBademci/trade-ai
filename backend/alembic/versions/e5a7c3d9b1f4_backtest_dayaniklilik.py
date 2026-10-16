"""Backtest kosularina baslangic gunu hassasiyeti sonucu.

- backtest_run.robustness (JSON, bos olabilir): ayni ayarlarla birkac islem gunu
  kaydirilmis baslangiclardan yapilan ek kosularin XU100'e gore farki.

Revision ID: e5a7c3d9b1f4
Revises: d4b8e2f1a6c3
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5a7c3d9b1f4"
down_revision: str | None = "d4b8e2f1a6c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_run",
        sa.Column("robustness", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backtest_run", "robustness")
