"""Hesap, oturum, davet kodu ve yonetici kullanici listesi API semalari."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AppUser, InviteCode


class ClientInfo(BaseModel):
    # Web sunucusu iletir; API yalniz servis anahtariyla cagrildigi icin guvenilir.
    client_ip: str = Field(default="unknown", max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)


class RegisterIn(ClientInfo):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)
    display_name: str = Field(default="", max_length=64)
    invite_code: str = Field(default="", max_length=64)
    accept_terms: bool = False


class LoginIn(ClientInfo):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class EmailIn(ClientInfo):
    email: str = Field(max_length=320)


class TokenIn(ClientInfo):
    token: str = Field(min_length=16, max_length=128)


class PasswordResetConfirmIn(TokenIn):
    password: str = Field(max_length=256)


class AcceptedOut(BaseModel):
    status: str
    message: str


class AuthConfigOut(BaseModel):
    registration_mode: Literal["invite", "open", "closed"]
    terms_version: str
    password_min_length: int


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    email_verified: bool
    created_at: datetime | None
    last_login_at: datetime | None

    @classmethod
    def from_user(cls, user: AppUser) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class LoginOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class PasswordConfirmIn(BaseModel):
    password: str = Field(max_length=256)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    ip_address: str | None
    current: bool = False


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: str
    status: str
    email_verified_at: datetime | None
    created_at: datetime | None
    last_login_at: datetime | None
    invite_code_id: int | None


class AdminUsersOut(BaseModel):
    total: int
    verified: int
    signups_24h: int
    smtp_configured: bool
    registration_mode: str
    users: list[AdminUserOut]


class AdminUserUpdate(BaseModel):
    status: Literal["ACTIVE", "DISABLED"] | None = None
    role: Literal["user", "admin"] | None = None
    verify_email: bool = False


class InviteCreate(BaseModel):
    note: str = Field(default="", max_length=128)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class InviteOut(BaseModel):
    id: int
    code: str
    note: str
    max_uses: int
    used_count: int
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime | None
    state: Literal["active", "used", "expired", "revoked"]

    @classmethod
    def from_invite(cls, invite: InviteCode, now: datetime) -> InviteOut:
        from app.auth.service import as_aware

        if invite.revoked_at is not None:
            state = "revoked"
        elif invite.used_count >= invite.max_uses:
            state = "used"
        elif invite.expires_at is not None and as_aware(invite.expires_at) <= now:
            state = "expired"
        else:
            state = "active"
        return cls(
            id=invite.id,
            code=invite.code,
            note=invite.note,
            max_uses=invite.max_uses,
            used_count=invite.used_count,
            expires_at=invite.expires_at,
            revoked_at=invite.revoked_at,
            created_at=invite.created_at,
            state=state,
        )
