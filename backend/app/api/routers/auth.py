"""Kayit, giris, e-posta dogrulama ve parola sifirlama uclari.

Yalniz web sunucusu cagirir (`X-Admin-Token`); istemci IP'si govdede gelir ve
hiz sinirlari ona gore sayilir. Kayit ve parola sifirlama, e-posta kayitli
olsun olmasin ayni yaniti verir.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.schedules import require_admin_token
from app.auth import google, ratelimit
from app.auth.security import PASSWORD_MIN_LENGTH, normalize_email
from app.auth.service import (
    TERMS_VERSION,
    AuthError,
    authenticate,
    create_session,
    register,
    registration_mode,
    request_password_reset,
    resend_verification,
    reset_password,
    verify_email,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.mail.messages import (
    account_exists_mail,
    password_changed_mail,
    password_reset_mail,
    verification_mail,
)
from app.mail.sender import enqueue_mail
from app.schemas.auth import (
    AcceptedOut,
    AuthConfigOut,
    EmailIn,
    GoogleSignInIn,
    GoogleStartOut,
    LoginIn,
    LoginOut,
    PasswordResetConfirmIn,
    RegisterIn,
    TokenIn,
    UserOut,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    dependencies=[Depends(require_admin_token)],
)
DB = Annotated[AsyncSession, Depends(get_db)]


def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def from_auth_error(exc: AuthError) -> HTTPException:
    return http_error(exc.status_code, exc.code, exc.message)


TOO_MANY_ATTEMPTS = ("rate_limited", "Çok fazla deneme yapıldı. Biraz sonra tekrar dene.")
INVALID_TOKEN = ("invalid_token", "Bağlantı geçersiz, süresi dolmuş ya da daha önce kullanılmış.")


def _email_or_422(raw: str) -> str:
    email = normalize_email(raw)
    if email is None:
        raise http_error(422, "invalid_email", "Geçerli bir e-posta adresi gir.")
    return email


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    return AuthConfigOut(
        registration_mode=await registration_mode(),
        terms_version=TERMS_VERSION,
        password_min_length=PASSWORD_MIN_LENGTH,
        google_enabled=google.google_enabled(get_settings()),
    )


def _google_settings():
    settings = get_settings()
    if not google.google_enabled(settings):
        raise http_error(404, "google_disabled", "Google ile giriş etkin değil.")
    return settings


@router.post("/google/start", response_model=GoogleStartOut)
async def google_start() -> GoogleStartOut:
    """Yetki adresi ve tek kullanimlik degerler; web bunlari kisa omurlu cerezde saklar."""
    started = google.start(_google_settings())
    return GoogleStartOut(
        url=started.url,
        state=started.state,
        code_verifier=started.code_verifier,
        nonce=started.nonce,
    )


@router.post("/google", response_model=LoginOut)
async def google_sign_in(body: GoogleSignInIn, db: DB) -> LoginOut:
    settings = _google_settings()
    if await ratelimit.is_limited(ratelimit.LOGIN_FAILURES_PER_IP, body.client_ip) or (
        body.accept_terms and await ratelimit.is_limited(ratelimit.REGISTER_PER_IP, body.client_ip)
    ):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    try:
        profile = await google.exchange_code(
            settings, code=body.code, code_verifier=body.code_verifier, nonce=body.nonce
        )
        user, created = await google.sign_in(
            db, profile, invite_code=body.invite_code, accept_terms=body.accept_terms
        )
    except AuthError as exc:
        if exc.code in {"google_failed", "invalid_invite"}:
            await ratelimit.hit(ratelimit.LOGIN_FAILURES_PER_IP, body.client_ip)
        raise from_auth_error(exc) from exc
    if created:
        await ratelimit.hit(ratelimit.REGISTER_PER_IP, body.client_ip)
    token, session = await create_session(
        db, user, user_agent=body.user_agent, ip_address=body.client_ip
    )
    return LoginOut(token=token, expires_at=session.expires_at, user=UserOut.from_user(user))


@router.post("/register", response_model=AcceptedOut, status_code=status.HTTP_202_ACCEPTED)
async def register_user(body: RegisterIn, db: DB) -> AcceptedOut:
    email = _email_or_422(body.email)
    if await ratelimit.is_limited(ratelimit.REGISTER_PER_IP, body.client_ip):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    try:
        outcome = await register(
            db,
            email=email,
            password=body.password,
            display_name=body.display_name,
            invite_code=body.invite_code,
            accepted_terms=body.accept_terms,
        )
    except AuthError as exc:
        # Yazim hatalari hakki yemesin; davet kodu denemesi ise sayilir.
        if exc.code == "invalid_invite":
            await ratelimit.hit(ratelimit.REGISTER_PER_IP, body.client_ip)
        raise from_auth_error(exc) from exc
    await ratelimit.hit(ratelimit.REGISTER_PER_IP, body.client_ip)
    if await ratelimit.take(ratelimit.MAIL_PER_EMAIL, email):
        await enqueue_mail(
            verification_mail(email, outcome.verify_token)
            if outcome.created and outcome.verify_token
            else account_exists_mail(email)
        )
    return AcceptedOut(
        status="pending_verification",
        message=(
            "Doğrulama bağlantısını e-posta adresine gönderdik. Hesabını etkinleştirmek "
            "için gelen kutunu (ve gereksiz klasörünü) kontrol et."
        ),
    )


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, db: DB) -> LoginOut:
    email = normalize_email(body.email)
    if email is None:
        raise http_error(401, "invalid_credentials", "E-posta veya parola hatalı.")
    if await ratelimit.is_limited(
        ratelimit.LOGIN_FAILURES_PER_IP, body.client_ip
    ) or await ratelimit.is_limited(ratelimit.LOGIN_FAILURES_PER_EMAIL, email):
        raise http_error(
            429, "rate_limited", "Çok fazla hatalı deneme. 15 dakika sonra tekrar dene."
        )
    try:
        user = await authenticate(db, email, body.password)
    except AuthError as exc:
        if exc.code == "invalid_credentials":
            await ratelimit.hit(ratelimit.LOGIN_FAILURES_PER_IP, body.client_ip)
            await ratelimit.hit(ratelimit.LOGIN_FAILURES_PER_EMAIL, email)
        raise from_auth_error(exc) from exc
    token, session = await create_session(
        db, user, user_agent=body.user_agent, ip_address=body.client_ip
    )
    return LoginOut(token=token, expires_at=session.expires_at, user=UserOut.from_user(user))


@router.post("/verify-email", response_model=AcceptedOut)
async def confirm_email(body: TokenIn, db: DB) -> AcceptedOut:
    if await ratelimit.is_limited(ratelimit.TOKEN_FAILURES_PER_IP, body.client_ip):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    if await verify_email(db, body.token) is None:
        await ratelimit.hit(ratelimit.TOKEN_FAILURES_PER_IP, body.client_ip)
        raise http_error(400, *INVALID_TOKEN)
    return AcceptedOut(
        status="verified", message="E-posta adresin doğrulandı. Artık giriş yapabilirsin."
    )


@router.post(
    "/resend-verification", response_model=AcceptedOut, status_code=status.HTTP_202_ACCEPTED
)
async def resend_verification_mail(body: EmailIn, db: DB) -> AcceptedOut:
    email = _email_or_422(body.email)
    if not await ratelimit.take(ratelimit.MAIL_PER_IP, body.client_ip):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    token = await resend_verification(db, email)
    if token and await ratelimit.take(ratelimit.MAIL_PER_EMAIL, email):
        await enqueue_mail(verification_mail(email, token))
    return AcceptedOut(
        status="accepted",
        message="Bu adresle doğrulanmamış bir hesap varsa yeni bağlantıyı gönderdik.",
    )


@router.post(
    "/password-reset/request", response_model=AcceptedOut, status_code=status.HTTP_202_ACCEPTED
)
async def password_reset_request(body: EmailIn, db: DB) -> AcceptedOut:
    email = _email_or_422(body.email)
    if not await ratelimit.take(ratelimit.MAIL_PER_IP, body.client_ip):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    token = await request_password_reset(db, email)
    if token and await ratelimit.take(ratelimit.MAIL_PER_EMAIL, email):
        await enqueue_mail(password_reset_mail(email, token))
    return AcceptedOut(
        status="accepted",
        message="Bu adresle bir hesap varsa parola sıfırlama bağlantısını gönderdik.",
    )


@router.post("/password-reset/confirm", response_model=AcceptedOut)
async def password_reset_confirm(body: PasswordResetConfirmIn, db: DB) -> AcceptedOut:
    if await ratelimit.is_limited(ratelimit.TOKEN_FAILURES_PER_IP, body.client_ip):
        raise http_error(429, *TOO_MANY_ATTEMPTS)
    try:
        user = await reset_password(db, body.token, body.password)
    except AuthError as exc:
        raise from_auth_error(exc) from exc
    if user is None:
        await ratelimit.hit(ratelimit.TOKEN_FAILURES_PER_IP, body.client_ip)
        raise http_error(400, *INVALID_TOKEN)
    await enqueue_mail(password_changed_mail(user.email))
    return AcceptedOut(
        status="password_reset",
        message="Parolan değiştirildi ve tüm oturumlar kapatıldı. Yeni parolanla giriş yapabilirsin.",
    )
