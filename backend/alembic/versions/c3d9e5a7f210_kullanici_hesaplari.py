"""Kullanici hesaplari: kullanici, oturum, tek kullanimlik token, davet kodu ve
kullaniciya bagli izleme listesi.

Mevcut tablolara dokunmaz; yoneticinin bildirim listesi (`watchlist_item`)
oldugu gibi kalir.

Revision ID: c3d9e5a7f210
Revises: b2c7f4e19a58
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d9e5a7f210"
down_revision: str | None = "b2c7f4e19a58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str, *, nullable: bool = False, default: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default else None,
    )


def upgrade() -> None:
    op.create_table(
        "invite_code",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("note", sa.String(128), nullable=False, server_default=""),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        _timestamp("expires_at", nullable=True),
        _timestamp("revoked_at", nullable=True),
        _timestamp("created_at", default=True),
        sa.CheckConstraint("max_uses >= 1", name="ck_invite_code_max_uses"),
        sa.CheckConstraint("used_count >= 0", name="ck_invite_code_used_count"),
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        _timestamp("email_verified_at", nullable=True),
        sa.Column("terms_version", sa.String(16), nullable=True),
        _timestamp("terms_accepted_at", nullable=True),
        sa.Column(
            "invite_code_id",
            sa.BigInteger(),
            sa.ForeignKey("invite_code.id", ondelete="SET NULL"),
            nullable=True,
        ),
        _timestamp("created_at", default=True),
        _timestamp("updated_at", default=True),
        _timestamp("last_login_at", nullable=True),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_app_user_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_app_user_status"),
    )
    op.create_index("uq_app_user_email", "app_user", ["email"], unique=True)
    op.create_table(
        "user_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_agent", sa.String(256), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        _timestamp("created_at"),
        _timestamp("last_seen_at"),
        _timestamp("expires_at"),
    )
    op.create_index("ix_user_session_user", "user_session", ["user_id"])
    op.create_table(
        "user_token",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        _timestamp("created_at"),
        _timestamp("expires_at"),
        _timestamp("used_at", nullable=True),
        sa.CheckConstraint(
            "purpose IN ('EMAIL_VERIFY', 'PASSWORD_RESET')", name="ck_user_token_purpose"
        ),
    )
    op.create_index("ix_user_token_user_purpose", "user_token", ["user_id", "purpose"])
    op.create_table(
        "user_watchlist_item",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(16), primary_key=True),
        _timestamp("added_at", default=True),
    )


def downgrade() -> None:
    op.drop_table("user_watchlist_item")
    op.drop_index("ix_user_token_user_purpose", table_name="user_token")
    op.drop_table("user_token")
    op.drop_index("ix_user_session_user", table_name="user_session")
    op.drop_table("user_session")
    op.drop_index("uq_app_user_email", table_name="app_user")
    op.drop_table("app_user")
    op.drop_table("invite_code")
