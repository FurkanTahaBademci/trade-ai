"""Kullanici hesaplari, oturumlar, tek kullanimlik token'lar ve davet kodlari.

Parola ve token'lar asla duz metin saklanmaz: parola argon2id ozeti, oturum ve
e-posta/parola token'lari sha256 ozeti olarak tutulur (bkz. app/auth/).
E-posta adresi her zaman kucuk harfe cevrilip yazilir; tekillik bu bicim
uzerinden saglanir.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# SQLite (testler) yalniz INTEGER PRIMARY KEY'i otomatik artirir.
ID_TYPE = BigInteger().with_variant(Integer, "sqlite")

USER_ROLES = ("user", "admin")
USER_STATUSES = ("ACTIVE", "DISABLED")
TOKEN_PURPOSES = ("EMAIL_VERIFY", "PASSWORD_RESET", "TELEGRAM_LINK")
IDENTITY_PROVIDERS = ("google",)


class InviteCode(Base):
    __tablename__ = "invite_code"
    __table_args__ = (
        CheckConstraint("max_uses >= 1", name="ck_invite_code_max_uses"),
        CheckConstraint("used_count >= 0", name="ck_invite_code_used_count"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    note: Mapped[str] = mapped_column(String(128), default="")
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_app_user_role"),
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_app_user_status"),
        Index("uq_app_user_email", "email", unique=True),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terms_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invite_code_id: Mapped[int | None] = mapped_column(
        ID_TYPE, ForeignKey("invite_code.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (Index("ix_user_session_user", "user_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserToken(Base):
    __tablename__ = "user_token"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('EMAIL_VERIFY', 'PASSWORD_RESET', 'TELEGRAM_LINK')",
            name="ck_user_token_purpose",
        ),
        Index("ix_user_token_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserWatchlistItem(Base):
    """Kullanicinin hesabina bagli izleme listesi.

    Yoneticinin bildirim listesi (`watchlist_item`) ayri kalir; bildirimler
    yalniz onu izler.
    """

    __tablename__ = "user_watchlist_item"

    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserIdentity(Base):
    """Harici kimlik saglayicisi baglantisi (Google). `subject` saglayicinin kalici kimligidir."""

    __tablename__ = "user_identity"
    __table_args__ = (
        CheckConstraint("provider IN ('google')", name="ck_user_identity_provider"),
        Index("uq_user_identity_subject", "provider", "subject", unique=True),
        Index("uq_user_identity_user_provider", "user_id", "provider", unique=True),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(254), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserAlertPref(Base):
    """Kisisel bildirim tercihleri: Telegram baglantisi ve gunluk ozet kanallari.

    `last_digest_on`, ayni islem gunu icin ozetin ikinci kez gitmesini engeller.
    """

    __tablename__ = "user_alert_pref"

    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_linked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    telegram_instant: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_digest: Mapped[bool] = mapped_column(Boolean, default=True)
    email_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    last_digest_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
