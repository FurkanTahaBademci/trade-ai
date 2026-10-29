"""Google ile giris: OpenID Connect yetki kodu akisi (PKCE) ve hesap eslestirme.

Akis:
1. Web `POST /api/auth/google/start` ile yetki adresini, `state`, PKCE
   dogrulayicisini ve `nonce`'u alir; bunlari kisa omurlu HttpOnly cerezde tutar.
2. Google kullaniciyi `<PUBLIC_BASE_URL>/giris/google/callback`'e dondurur.
3. Web kodu `POST /api/auth/google`'a (giris/kayit) ya da
   `POST /api/me/identities/google`'a (hesaba baglama) iletir. API kodu istemci
   sirriyla token'a cevirir ve kimligi dogrular.

ID token Google'in token ucundan dogrudan TLS ile alindigi icin imzasi ayrica
dogrulanmaz (OIDC Core 3.1.3.7); iss, aud, exp, nonce ve email_verified denetlenir.

Var olan e-posta hesabina otomatik baglama yalniz Google'in o adres icin yetkili
oldugu durumda yapilir (gmail.com ya da Workspace `hd`); digerlerinde kullanici
parolasiyla girip Hesabim'dan baglar.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import normalize_email
from app.auth.service import (
    TERMS_VERSION,
    AuthError,
    claim_invite,
    find_user_by_email,
    registration_mode,
    revoke_sessions,
    utcnow,
)
from app.core.config import Settings
from app.models import AppUser, UserIdentity

logger = structlog.get_logger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
CALLBACK_PATH = "/giris/google/callback"
CLOCK_SKEW_SECONDS = 300
PROVIDER = "google"
GOOGLE_MAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})

FAILED = AuthError("google_failed", "Google girişi tamamlanamadı. Lütfen tekrar dene.", 400)


@dataclass(frozen=True)
class GoogleStart:
    url: str
    state: str
    code_verifier: str
    nonce: str


@dataclass(frozen=True)
class GoogleProfile:
    subject: str
    email: str
    name: str
    hosted_domain: str | None = None

    @property
    def authoritative(self) -> bool:
        """Google bu adresin sahibini kesin biliyor mu (gmail ya da Workspace alani)."""
        domain = self.email.rpartition("@")[2]
        return domain in GOOGLE_MAIL_DOMAINS or (self.hosted_domain or "").lower() == domain


def google_enabled(settings: Settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def redirect_uri(settings: Settings) -> str:
    return settings.public_base_url.rstrip("/") + CALLBACK_PATH


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def start(settings: Settings) -> GoogleStart:
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(16)
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return GoogleStart(
        url=f"{AUTHORIZE_URL}?{query}", state=state, code_verifier=verifier, nonce=nonce
    )


def _claims(id_token: str) -> dict[str, Any]:
    try:
        payload = id_token.split(".")[1]
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(decoded)
    except (IndexError, ValueError, binascii.Error) as exc:
        raise FAILED from exc
    if not isinstance(claims, dict):
        raise FAILED
    return claims


def parse_id_token(
    id_token: str, *, client_id: str, nonce: str, now: datetime | None = None
) -> GoogleProfile:
    claims = _claims(id_token)
    now_ts = (now or datetime.now(UTC)).timestamp()
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    valid = (
        claims.get("iss") in ISSUERS
        and client_id in audiences
        and isinstance(claims.get("exp"), int | float)
        and claims["exp"] + CLOCK_SKEW_SECONDS > now_ts
        and secrets.compare_digest(str(claims.get("nonce", "")), nonce)
        and bool(claims.get("sub"))
    )
    if not valid:
        logger.warning("google_id_token_rejected")
        raise FAILED
    email = normalize_email(str(claims.get("email") or ""))
    if email is None or claims.get("email_verified") not in (True, "true"):
        raise AuthError(
            "google_email_unverified",
            "Google hesabının e-posta adresi doğrulanmamış; bu hesapla giriş yapılamaz.",
            400,
        )
    return GoogleProfile(
        subject=str(claims["sub"])[:255],
        email=email,
        name=str(claims.get("name") or "").strip()[:64],
        hosted_domain=str(claims["hd"]) if claims.get("hd") else None,
    )


async def exchange_code(
    settings: Settings,
    *,
    code: str,
    code_verifier: str,
    nonce: str,
    client: httpx.AsyncClient | None = None,
) -> GoogleProfile:
    """Yetki kodunu Google token ucunda kimlige cevirir."""
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=10)
    try:
        response = await http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri(settings),
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
        )
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("google_token_exchange_failed", error=type(exc).__name__)
        raise FAILED from exc
    finally:
        if owns_client:
            await http.aclose()
    if not response.is_success or not isinstance(body, dict) or not body.get("id_token"):
        error = body.get("error") if isinstance(body, dict) else None
        logger.warning("google_token_exchange_failed", status=response.status_code, error=error)
        raise FAILED
    return parse_id_token(body["id_token"], client_id=settings.google_client_id, nonce=nonce)


async def _identity(db: AsyncSession, subject: str) -> UserIdentity | None:
    return await db.scalar(
        select(UserIdentity).where(
            UserIdentity.provider == PROVIDER, UserIdentity.subject == subject
        )
    )


def _ensure_active(user: AppUser) -> None:
    if user.status != "ACTIVE":
        raise AuthError("account_disabled", "Bu hesap devre dışı bırakılmış.", 403)


async def sign_in(
    db: AsyncSession, profile: GoogleProfile, *, invite_code: str, accept_terms: bool
) -> tuple[AppUser, bool]:
    """Google kimligiyle giris; gerekirse hesap baglar ya da acar. (kullanici, yeni_mi)."""
    now = utcnow()
    identity = await _identity(db, profile.subject)
    if identity is not None:
        user = await db.get(AppUser, identity.user_id)
        if user is None:
            raise FAILED
        _ensure_active(user)
        identity.email = profile.email
        identity.last_used_at = now
        if user.email_verified_at is None and user.email == profile.email:
            user.email_verified_at = now
        return user, False

    user = await find_user_by_email(db, profile.email)
    if user is not None:
        if not profile.authoritative:
            raise AuthError(
                "link_required",
                "Bu e-postayla kayıtlı bir hesap var. Parolanla giriş yapıp Hesabım "
                "sayfasından Google hesabını bağlayabilirsin.",
                409,
            )
        _ensure_active(user)
        if user.email_verified_at is None:
            # Dogrulanmamis hesabi baskasi acmis olabilir: adresin sahibi Google ile
            # geldi, onceden konmus parola gecersiz olur.
            user.password_hash = None
            user.email_verified_at = now
            await revoke_sessions(db, user.id)
        db.add(
            UserIdentity(
                user_id=user.id,
                provider=PROVIDER,
                subject=profile.subject,
                email=profile.email,
                last_used_at=now,
            )
        )
        logger.info("google_identity_linked", user_id=user.id, automatic=True)
        return user, False

    mode = await registration_mode()
    if mode == "closed":
        raise AuthError("registration_closed", "Yeni kayıtlar şu an kapalı.", 403)
    if not accept_terms:
        raise AuthError(
            "signup_required",
            "Bu Google hesabıyla kayıtlı bir hesap yok. Kayıt sayfasında koşulları "
            "onaylayıp “Google ile kayıt ol”u kullan.",
            404,
        )
    invite = await claim_invite(db, invite_code) if mode == "invite" else None
    user = AppUser(
        email=profile.email,
        password_hash=None,
        display_name=profile.name or profile.email.partition("@")[0][:64],
        role="user",
        status="ACTIVE",
        email_verified_at=now,
        terms_version=TERMS_VERSION,
        terms_accepted_at=now,
        invite_code_id=invite.id if invite else None,
    )
    db.add(user)
    try:
        await db.flush()
        db.add(
            UserIdentity(
                user_id=user.id,
                provider=PROVIDER,
                subject=profile.subject,
                email=profile.email,
                last_used_at=now,
            )
        )
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()  # ayni e-posta/kimlikle es zamanli kayit
        raise FAILED from exc
    logger.info("google_account_created", user_id=user.id)
    return user, True


async def link(db: AsyncSession, user: AppUser, profile: GoogleProfile) -> None:
    existing = await _identity(db, profile.subject)
    if existing is not None:
        if existing.user_id != user.id:
            raise AuthError(
                "identity_in_use", "Bu Google hesabı başka bir trade-ai hesabına bağlı.", 409
            )
        existing.email = profile.email
        existing.last_used_at = utcnow()
        await db.commit()
        return
    current = await db.scalar(
        select(UserIdentity).where(
            UserIdentity.user_id == user.id, UserIdentity.provider == PROVIDER
        )
    )
    if current is not None:
        raise AuthError(
            "already_linked",
            "Hesabına zaten başka bir Google hesabı bağlı; önce onu kaldır.",
            409,
        )
    db.add(
        UserIdentity(
            user_id=user.id,
            provider=PROVIDER,
            subject=profile.subject,
            email=profile.email,
            last_used_at=utcnow(),
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise FAILED from exc
    logger.info("google_identity_linked", user_id=user.id, automatic=False)


async def unlink(db: AsyncSession, user: AppUser) -> bool:
    identity = await db.scalar(
        select(UserIdentity).where(
            UserIdentity.user_id == user.id, UserIdentity.provider == PROVIDER
        )
    )
    if identity is None:
        return False
    if not user.password_hash:
        raise AuthError(
            "password_required",
            "Google bağlantısını kaldırmadan önce bir parola belirle; yoksa hesabına giriş "
            "yapamazsın.",
            409,
        )
    await db.delete(identity)
    await db.commit()
    return True
