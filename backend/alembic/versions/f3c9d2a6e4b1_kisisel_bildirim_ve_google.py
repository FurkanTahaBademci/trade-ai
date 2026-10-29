"""Kisisel bildirim tercihleri, Google kimlik baglantisi ve Telegram baglama token'i.

`user_alert_pref` kullanici basina tek satirdir (Telegram sohbeti, anlik
bildirim ve gunluk ozet kanallari). `user_identity` harici saglayici
(Google) hesabini kullaniciya baglar. `user_token.purpose` Telegram baglama
kodunu da kabul eder.

Revision ID: f3c9d2a6e4b1
Revises: e2a8c4f1b7d9
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3c9d2a6e4b1"
down_revision: str | None = "e2a8c4f1b7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str, *, nullable: bool = False, default: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default else None,
    )


def _user_fk(*, primary_key: bool = False) -> sa.Column:
    return sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=primary_key,
        nullable=False,
    )


def upgrade() -> None:
    op.drop_constraint("ck_user_token_purpose", "user_token", type_="check")
    op.create_check_constraint(
        "ck_user_token_purpose",
        "user_token",
        "purpose IN ('EMAIL_VERIFY', 'PASSWORD_RESET', 'TELEGRAM_LINK')",
    )
    op.create_table(
        "user_identity",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _user_fk(),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        _timestamp("created_at", default=True),
        _timestamp("last_used_at", nullable=True),
        sa.CheckConstraint("provider IN ('google')", name="ck_user_identity_provider"),
    )
    op.create_index(
        "uq_user_identity_subject", "user_identity", ["provider", "subject"], unique=True
    )
    op.create_index(
        "uq_user_identity_user_provider", "user_identity", ["user_id", "provider"], unique=True
    )
    op.create_table(
        "user_alert_pref",
        _user_fk(primary_key=True),
        sa.Column("telegram_chat_id", sa.String(32), nullable=True),
        sa.Column("telegram_username", sa.String(64), nullable=True),
        _timestamp("telegram_linked_at", nullable=True),
        sa.Column("telegram_instant", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("telegram_digest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_digest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_digest_on", sa.Date(), nullable=True),
        _timestamp("updated_at", default=True),
    )
    op.create_index("ix_user_alert_pref_telegram_chat_id", "user_alert_pref", ["telegram_chat_id"])


def downgrade() -> None:
    op.drop_index("ix_user_alert_pref_telegram_chat_id", table_name="user_alert_pref")
    op.drop_table("user_alert_pref")
    op.drop_index("uq_user_identity_user_provider", table_name="user_identity")
    op.drop_index("uq_user_identity_subject", table_name="user_identity")
    op.drop_table("user_identity")
    op.execute("DELETE FROM user_token WHERE purpose = 'TELEGRAM_LINK'")
    op.drop_constraint("ck_user_token_purpose", "user_token", type_="check")
    op.create_check_constraint(
        "ck_user_token_purpose", "user_token", "purpose IN ('EMAIL_VERIFY', 'PASSWORD_RESET')"
    )
