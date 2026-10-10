"""KAP bildirimine olay tarihi (genel kurul gunu, kar payi hak kullanim gunu).

Takvim olaylari yayin tarihi yerine bu tarihe yerlesir. Eski kayitlar
`python -m scripts.run_once kap-event-dates` ile doldurulur.

Revision ID: a3c5e7f92b18
Revises: f2b8c6d14e57
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c5e7f92b18"
down_revision: str | None = "f2b8c6d14e57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kap_disclosure", sa.Column("event_date", sa.Date(), nullable=True))
    op.add_column("kap_disclosure", sa.Column("event_detail", sa.String(160), nullable=True))
    op.create_index("ix_kap_disclosure_event_date", "kap_disclosure", ["event_date"])


def downgrade() -> None:
    op.drop_index("ix_kap_disclosure_event_date", table_name="kap_disclosure")
    op.drop_column("kap_disclosure", "event_detail")
    op.drop_column("kap_disclosure", "event_date")
