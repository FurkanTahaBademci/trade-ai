"""Haber makale tablosu.

Revision ID: d3f6a81c2e90
Revises: a7e2c4f98b11
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d3f6a81c2e90"
down_revision: str | None = "a7e2c4f98b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_article",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_guid", sa.String(length=2048), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_entry", sa.JSON(), nullable=False),
        sa.Column(
            "fetched_at",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index("ix_news_article_published_at", "news_article", ["published_at"])
    op.create_index(
        "ix_news_article_source_published",
        "news_article",
        ["source", "published_at"],
    )
    op.create_index(
        "ix_news_article_ticker_codes_gin",
        "news_article",
        ["ticker_codes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_news_article_ticker_codes_gin", table_name="news_article")
    op.drop_index("ix_news_article_source_published", table_name="news_article")
    op.drop_index("ix_news_article_published_at", table_name="news_article")
    op.drop_table("news_article")
