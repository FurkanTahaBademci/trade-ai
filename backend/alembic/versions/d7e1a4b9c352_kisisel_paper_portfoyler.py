"""Kisisel paper portfoyler: sahip, tur (strateji/manuel), ayarlar ve manuel emirler.

Mevcut model portfoy `owner_id` bos ve `kind='STRATEGY'` olarak kalir; ayarlari
bos oldugu icin davranisi degismez. Ad tekilligi, model portfoy icin adla,
kullanici portfoyleri icin (sahip, ad) ile saglanir.

Revision ID: d7e1a4b9c352
Revises: c3d9e5a7f210
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d7e1a4b9c352"
down_revision: str | None = "c3d9e5a7f210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_NAME_UNIQUE = """
DO $$
DECLARE constraint_name text;
BEGIN
    FOR constraint_name IN
        SELECT con.conname
        FROM pg_constraint AS con
        JOIN pg_class AS rel ON rel.oid = con.conrelid
        JOIN pg_attribute AS att ON att.attrelid = rel.oid AND att.attname = 'name'
        WHERE rel.relname = 'paper_portfolio'
          AND con.contype = 'u'
          AND con.conkey = ARRAY[att.attnum]
    LOOP
        EXECUTE format('ALTER TABLE paper_portfolio DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.add_column(
        "paper_portfolio",
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "paper_portfolio",
        sa.Column("kind", sa.String(16), nullable=False, server_default="STRATEGY"),
    )
    op.add_column("paper_portfolio", sa.Column("config", postgresql.JSONB(), nullable=True))
    op.add_column("paper_portfolio", sa.Column("started_on", sa.Date(), nullable=True))
    op.add_column(
        "paper_portfolio", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("paper_portfolio", sa.Column("last_error", sa.String(500), nullable=True))
    op.create_check_constraint(
        "ck_paper_portfolio_kind", "paper_portfolio", "kind IN ('STRATEGY', 'MANUAL')"
    )
    # Ilk migration'daki adsiz UniqueConstraint("name") PostgreSQL'de genelde
    # paper_portfolio_name_key adini alir; adi varsaymadan katalogdan bulunur.
    op.execute(_DROP_NAME_UNIQUE)
    op.create_index(
        "uq_paper_portfolio_system_name",
        "paper_portfolio",
        ["name"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )
    op.create_index(
        "uq_paper_portfolio_owner_name",
        "paper_portfolio",
        ["owner_id", "name"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NOT NULL"),
    )

    op.create_table(
        "paper_order",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "portfolio_id",
            sa.BigInteger(),
            sa.ForeignKey("paper_portfolio.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ticker",
            sa.String(16),
            sa.ForeignKey("instrument.ticker", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("amount", sa.Numeric(30, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("client_order_id", sa.String(64), nullable=True),
        sa.Column("not_before", sa.Date(), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column(
            "trade_id",
            sa.BigInteger(),
            sa.ForeignKey("paper_trade.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fill_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_paper_order_side"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED')",
            name="ck_paper_order_status",
        ),
        sa.CheckConstraint(
            "quantity IS NOT NULL OR amount IS NOT NULL", name="ck_paper_order_size"
        ),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_paper_order_quantity"),
        sa.CheckConstraint("amount IS NULL OR amount > 0", name="ck_paper_order_amount"),
        sa.UniqueConstraint("portfolio_id", "client_order_id", name="uq_paper_order_client_id"),
    )
    op.create_index("ix_paper_order_portfolio_status", "paper_order", ["portfolio_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_paper_order_portfolio_status", table_name="paper_order")
    op.drop_table("paper_order")
    # Kullanici portfoyleri model portfoyle ayni adi tasiyabilir; tek tekillige
    # donmeden once silinir.
    op.execute("DELETE FROM paper_portfolio WHERE owner_id IS NOT NULL")
    op.drop_index("uq_paper_portfolio_owner_name", table_name="paper_portfolio")
    op.drop_index("uq_paper_portfolio_system_name", table_name="paper_portfolio")
    op.create_unique_constraint("paper_portfolio_name_key", "paper_portfolio", ["name"])
    op.drop_constraint("ck_paper_portfolio_kind", "paper_portfolio", type_="check")
    for column in ("last_error", "last_run_at", "started_on", "config", "kind", "owner_id"):
        op.drop_column("paper_portfolio", column)
