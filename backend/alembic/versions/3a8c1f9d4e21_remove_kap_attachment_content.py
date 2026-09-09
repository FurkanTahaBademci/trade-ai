"""KAP ek dosya binary depolamasini kaldir.

Revision ID: 3a8c1f9d4e21
Revises: 7a6e9c4f2b10
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3a8c1f9d4e21"
down_revision: str | None = "7a6e9c4f2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("kap_attachment", "content")
    op.drop_column("kap_attachment", "size_bytes")
    op.drop_column("kap_attachment", "sha256")
    op.drop_column("kap_attachment", "downloaded_at")
    op.drop_column("kap_attachment", "download_error")


def downgrade() -> None:
    op.add_column(
        "kap_attachment",
        sa.Column("download_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "kap_attachment",
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kap_attachment",
        sa.Column("sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "kap_attachment",
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "kap_attachment",
        sa.Column("content", sa.LargeBinary(), nullable=True),
    )
