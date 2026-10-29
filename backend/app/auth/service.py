"""Hesap islemleri: kayit, giris, oturum, e-posta dogrulama ve parola sifirlama.

Hesap varligi disari sizdirilmaz: kayit ve parola sifirlama, e-posta kayitli
olsa da olmasa da ayni yaniti dondurur (fark yalniz giden e-postadadir).
Giris, e-posta dogrulanmadan acilmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_token,
    normalize_invite_code,
    password_problem,
    verify_password,
)
from app.core.config import get_settings
from app.core.dynamic_settings import resolve_settings
from app.models import AppUser, InviteCode, UserSession, UserToken

# Kullanim kosullari / aydinlatma metni degisince artir; kayitta saklanir.
TERMS_VERSION = "2026-10"
VERIFY_TOKEN_TTL = timedelta(hours=48)
RESET_TOKEN_TTL = timedelta(hours=1)
# Her istekte yazmamak icin "son gorulme" en fazla saatte bir guncellenir.
SESSION_TOUCH_INTERVAL = timedelta(hours=1)
REGISTRATION_MODES = ("invite", "open", "closed")


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RegisterOutcome:
    email: str
    created: bool
    verify_token: str | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_aware(value: datetime) -> datetime:
    # SQLite (testler) saat dilimini saklamaz; tum zamanlar UTC yazilir.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def registration_mode() -> str:
    try:
        mode = (await resolve_settings()).registration_mode
    except Exception:  # noqa: BLE001 - Redis yoksa .env varsayilani
        mode = get_settings().registration_mode
    return mode if mode in REGISTRATION_MODES else "closed"


async def find_user_by_email(db: AsyncSession, email: str) -> AppUser | None:
    return await db.scalar(select(AppUser).where(AppUser.email == email))


def _check_password(password: str) -> None:
    problem = password_problem(password)
    if problem:
        raise AuthError("weak_password", problem, 422)


async def claim_invite(db: AsyncSession, raw_code: str) -> InviteCode:
    code = normalize_invite_code(raw_code)
    invite = await db.scalar(select(InviteCode).where(InviteCode.code == code)) if code else None
    now = utcnow()
    usable = (
        invite is not None
        and invite.revoked_at is None
        and (invite.expires_at is None or as_aware(invite.expires_at) > now)
        and invite.used_count < invite.max_uses
    )
    if not usable:
        raise AuthError(
            "invalid_invite", "Davet kodu geçersiz, süresi dolmuş ya da kullanılmış.", 422
        )
    # Ayni koda es zamanli iki kayit kotayi asmasin.
    claimed = await db.execute(
        update(InviteCode)
        .where(InviteCode.id == invite.id, InviteCode.used_count < InviteCode.max_uses)
        .values(used_count=InviteCode.used_count + 1)
    )
    if claimed.rowcount != 1:
        raise AuthError(
            "invalid_invite", "Davet kodu geçersiz, süresi dolmuş ya da kullanılmış.", 422
        )
    return invite


async def issue_token(db: AsyncSession, user: AppUser, purpose: str, ttl: timedelta) -> str:
    # Ayni amacla verilmis eski, kullanilmamis baglantilar gecersiz olur.
    await db.execute(
        delete(UserToken).where(
            UserToken.user_id == user.id,
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
        )
    )
    raw, digest = new_token()
    now = utcnow()
    db.add(
        UserToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=digest,
            created_at=now,
            expires_at=now + ttl,
        )
    )
    return raw


async def consume_token(db: AsyncSession, raw: str, purpose: str) -> AppUser | None:
    row = await db.scalar(
        select(UserToken).where(
            UserToken.token_hash == hash_token(raw), UserToken.purpose == purpose
        )
    )
    now = utcnow()
    if row is None or row.used_at is not None or as_aware(row.expires_at) <= now:
        return None
    user = await db.get(AppUser, row.user_id)
    if user is None or user.status != "ACTIVE":
        return None
    row.used_at = now
    return user


async def register(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    invite_code: str,
    accepted_terms: bool,
) -> RegisterOutcome:
    mode = await registration_mode()
    if mode == "closed":
        raise AuthError("registration_closed", "Yeni kayıtlar şu an kapalı.", 403)
    if not accepted_terms:
        raise AuthError(
            "terms_required", "Kullanım koşullarını ve aydınlatma metnini onaylamalısın.", 422
        )
    _check_password(password)
    # Davet kodu hesap varligindan once denetlenir; kodu olmayan biri kayitli
    # e-postalari yoklayamasin.
    invite = await claim_invite(db, invite_code) if mode == "invite" else None
    # Ozet, kayitli e-postada da hesaplanir; yanit suresi hesap varligini ele vermesin.
    password_hash = await hash_password(password)
    if await find_user_by_email(db, email) is not None:
        await db.rollback()  # davet hakki harcanmasin
        return RegisterOutcome(email=email, created=False)

    now = utcnow()
    user = AppUser(
        email=email,
        password_hash=password_hash,
        display_name=display_name.strip()[:64] or email.partition("@")[0][:64],
        role="user",
        status="ACTIVE",
        terms_version=TERMS_VERSION,
        terms_accepted_at=now,
        invite_code_id=invite.id if invite else None,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()  # ayni e-postayla es zamanli kayit
        return RegisterOutcome(email=email, created=False)
    token = await issue_token(db, user, "EMAIL_VERIFY", VERIFY_TOKEN_TTL)
    await db.commit()
    return RegisterOutcome(email=email, created=True, verify_token=token)


async def verify_email(db: AsyncSession, raw: str) -> AppUser | None:
    user = await consume_token(db, raw, "EMAIL_VERIFY")
    if user is None:
        return None
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await db.commit()
    return user


async def resend_verification(db: AsyncSession, email: str) -> str | None:
    user = await find_user_by_email(db, email)
    if user is None or user.status != "ACTIVE" or user.email_verified_at is not None:
        return None
    token = await issue_token(db, user, "EMAIL_VERIFY", VERIFY_TOKEN_TTL)
    await db.commit()
    return token


async def authenticate(db: AsyncSession, email: str, password: str) -> AppUser:
    user = await find_user_by_email(db, email)
    valid = await verify_password(user.password_hash if user else None, password)
    if user is None or not valid:
        raise AuthError("invalid_credentials", "E-posta veya parola hatalı.", 401)
    if user.status != "ACTIVE":
        raise AuthError("account_disabled", "Bu hesap devre dışı bırakılmış.", 403)
    if user.email_verified_at is None:
        raise AuthError(
            "email_not_verified",
            "E-posta adresin henüz doğrulanmadı. Gelen kutundaki bağlantıyı aç.",
            403,
        )
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = await hash_password(password)
    return user


async def create_session(
    db: AsyncSession, user: AppUser, *, user_agent: str | None, ip_address: str | None
) -> tuple[str, UserSession]:
    raw, digest = new_token()
    now = utcnow()
    session = UserSession(
        user_id=user.id,
        token_hash=digest,
        user_agent=(user_agent or "")[:256] or None,
        ip_address=(ip_address or "")[:64] or None,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=get_settings().session_ttl_days),
    )
    user.last_login_at = now
    db.add(session)
    await db.commit()
    return raw, session


async def resolve_session(db: AsyncSession, raw: str) -> tuple[AppUser, UserSession] | None:
    row = (
        await db.execute(
            select(UserSession, AppUser)
            .join(AppUser, AppUser.id == UserSession.user_id)
            .where(UserSession.token_hash == hash_token(raw))
        )
    ).first()
    if row is None:
        return None
    session, user = row
    now = utcnow()
    if as_aware(session.expires_at) <= now:
        await db.delete(session)
        await db.commit()
        return None
    if user.status != "ACTIVE":
        return None
    if now - as_aware(session.last_seen_at) >= SESSION_TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.commit()
    return user, session


async def revoke_sessions(db: AsyncSession, user_id: int, *, keep_id: int | None = None) -> int:
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_id is not None:
        stmt = stmt.where(UserSession.id != keep_id)
    return (await db.execute(stmt)).rowcount or 0


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    user = await find_user_by_email(db, email)
    if user is None or user.status != "ACTIVE":
        return None
    token = await issue_token(db, user, "PASSWORD_RESET", RESET_TOKEN_TTL)
    await db.commit()
    return token


async def reset_password(db: AsyncSession, raw: str, new_password: str) -> AppUser | None:
    _check_password(new_password)
    user = await consume_token(db, raw, "PASSWORD_RESET")
    if user is None:
        return None
    user.password_hash = await hash_password(new_password)
    # Baglantiyi acan kisi e-postanin sahibidir.
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await revoke_sessions(db, user.id)
    await db.commit()
    return user


async def change_password(
    db: AsyncSession, user: AppUser, *, current: str, new: str, keep_session_id: int
) -> None:
    # Yalniz Google ile acilmis hesap ilk parolasini mevcut parola olmadan belirler.
    if user.password_hash and not await verify_password(user.password_hash, current):
        raise AuthError("invalid_credentials", "Mevcut parola hatalı.", 400)
    _check_password(new)
    user.password_hash = await hash_password(new)
    await revoke_sessions(db, user.id, keep_id=keep_session_id)
    await db.commit()


async def delete_account(
    db: AsyncSession, user: AppUser, *, password: str, confirm_email: str = ""
) -> None:
    if not user.password_hash:
        # Parolasiz (Google) hesap: onay olarak e-posta adresi yazilir.
        if (confirm_email or "").strip().lower() != user.email:
            raise AuthError("confirmation_mismatch", "Onay için e-posta adresini doğru yaz.", 400)
    elif not await verify_password(user.password_hash, password):
        raise AuthError("invalid_credentials", "Parola hatalı.", 400)
    await db.delete(user)
    await db.commit()


async def purge_expired(db: AsyncSession) -> dict[str, int]:
    """Suresi dolmus oturum ve token'lari siler (gunluk worker isi)."""
    now = utcnow()
    sessions = (await db.execute(delete(UserSession).where(UserSession.expires_at <= now))).rowcount
    tokens = (
        await db.execute(
            delete(UserToken).where((UserToken.expires_at <= now) | UserToken.used_at.is_not(None))
        )
    ).rowcount
    await db.commit()
    return {"sessions": sessions or 0, "tokens": tokens or 0}
