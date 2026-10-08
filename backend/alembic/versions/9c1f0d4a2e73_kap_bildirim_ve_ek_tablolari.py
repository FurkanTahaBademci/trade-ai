"""KAP bildirim ve ek tablolari

Revision ID: 9c1f0d4a2e73
Revises: 443eb1b2c69d
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9c1f0d4a2e73"
down_revision: str | None = "443eb1b2c69d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kap_disclosure",
        sa.Column("disclosure_index", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kap_title", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("disclosure_class", sa.String(length=32), nullable=True),
        sa.Column("disclosure_type", sa.String(length=32), nullable=True),
        sa.Column("disclosure_category", sa.String(length=32), nullable=True),
        sa.Column("ticker_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.Column("has_multi_language_support", sa.Boolean(), nullable=False),
        sa.Column("attachment_count", sa.Integer(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("raw_list_item", sa.JSON(), nullable=False),
        sa.Column("raw_detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("disclosure_index"),
    )
    op.create_index(
        op.f("ix_kap_disclosure_published_at"),
        "kap_disclosure",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kap_disclosure_disclosure_class"),
        "kap_disclosure",
        ["disclosure_class"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kap_disclosure_disclosure_type"),
        "kap_disclosure",
        ["disclosure_type"],
        unique=False,
    )
    op.create_index(
        "ix_kap_disclosure_ticker_codes_gin",
        "kap_disclosure",
        ["ticker_codes"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "kap_attachment",
        sa.Column("obj_id", sa.String(length=64), nullable=False),
        sa.Column("disclosure_index", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=1024), nullable=False),
        sa.Column("file_extension", sa.String(length=32), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_error", sa.Text(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["disclosure_index"],
            ["kap_disclosure.disclosure_index"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("obj_id"),
    )
    op.create_index(
        op.f("ix_kap_attachment_disclosure_index"),
        "kap_attachment",
        ["disclosure_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_kap_attachment_disclosure_index"),
        table_name="kap_attachment",
    )
    op.drop_table("kap_attachment")
    op.drop_index("ix_kap_disclosure_ticker_codes_gin", table_name="kap_disclosure")
    op.drop_index(op.f("ix_kap_disclosure_disclosure_type"), table_name="kap_disclosure")
    op.drop_index(op.f("ix_kap_disclosure_disclosure_class"), table_name="kap_disclosure")
    op.drop_index(op.f("ix_kap_disclosure_published_at"), table_name="kap_disclosure")
    op.drop_table("kap_disclosure")
