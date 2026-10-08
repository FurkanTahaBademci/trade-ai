"""Paper portfoy risk yonetimi alanlari.

Revision ID: b5e1d7a39c24
Revises: 3a8c1f9d4e21
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b5e1d7a39c24"
down_revision: str | None = "3a8c1f9d4e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_position", sa.Column("high_water_price", sa.Numeric(24, 8), nullable=True)
    )
    op.add_column("paper_trade", sa.Column("exit_reason", sa.String(24), nullable=True))
    # Mevcut islemler: satislar sinyal cikisi, alislar giris olarak etiketlenir.
    op.execute("UPDATE paper_trade SET exit_reason = 'signal' WHERE side = 'SELL'")


def downgrade() -> None:
    op.drop_column("paper_trade", "exit_reason")
    op.drop_column("paper_position", "high_water_price")
