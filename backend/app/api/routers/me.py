"""Oturum acmis kullanicinin kendi hesabi: profil, parola, oturumlar, izleme listesi.

Her uc `Authorization: Bearer <oturum token'i>` ister ve yalniz o kullanicinin
satirlarina dokunur.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import from_auth_error
from app.api.routers.watchlist import WatchlistIn, WatchlistOut, normalize_tickers
from app.auth import google
from app.auth.deps import CurrentAuth
from app.auth.service import AuthError, change_password, delete_account
from app.core.config import get_settings
from app.core.db import get_db
from app.mail.messages import password_changed_mail
from app.mail.sender import enqueue_mail
from app.models import UserIdentity, UserSession, UserWatchlistItem
from app.schemas.auth import (
    AcceptedOut,
    GoogleCodeIn,
    IdentityOut,
    PasswordChangeIn,
    PasswordConfirmIn,
    ProfileUpdate,
    SessionOut,
    UserOut,
)

router = APIRouter(prefix="/api/me", tags=["me"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=UserOut)
async def get_me(auth: CurrentAuth) -> UserOut:
    return UserOut.from_user(auth.user)


@router.patch("", response_model=UserOut)
async def update_me(body: ProfileUpdate, auth: CurrentAuth, db: DB) -> UserOut:
    auth.user.display_name = body.display_name.strip()[:64] or auth.user.display_name
    await db.commit()
    return UserOut.from_user(auth.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: CurrentAuth, db: DB) -> Response:
    await db.delete(auth.session)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password", response_model=AcceptedOut)
async def update_password(body: PasswordChangeIn, auth: CurrentAuth, db: DB) -> AcceptedOut:
    try:
        await change_password(
            db,
            auth.user,
            current=body.current_password,
            new=body.new_password,
            keep_session_id=auth.session.id,
        )
    except AuthError as exc:
        raise from_auth_error(exc) from exc
    await enqueue_mail(password_changed_mail(auth.user.email))
    return AcceptedOut(
        status="password_changed",
        message="Parolan değiştirildi. Diğer cihazlardaki oturumlar kapatıldı.",
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(auth: CurrentAuth, db: DB) -> list[SessionOut]:
    rows = await db.scalars(
        select(UserSession)
        .where(UserSession.user_id == auth.user.id)
        .order_by(UserSession.last_seen_at.desc(), UserSession.id.desc())
    )
    return [
        SessionOut.model_validate(row).model_copy(update={"current": row.id == auth.session.id})
        for row in rows.all()
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: int, auth: CurrentAuth, db: DB) -> Response:
    removed = await db.execute(
        delete(UserSession).where(UserSession.id == session_id, UserSession.user_id == auth.user.id)
    )
    if not removed.rowcount:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/revoke-others", response_model=AcceptedOut)
async def revoke_other_sessions(auth: CurrentAuth, db: DB) -> AcceptedOut:
    removed = await db.execute(
        delete(UserSession).where(
            UserSession.user_id == auth.user.id, UserSession.id != auth.session.id
        )
    )
    await db.commit()
    return AcceptedOut(status="ok", message=f"{removed.rowcount or 0} oturum kapatıldı.")


@router.post("/delete", response_model=AcceptedOut)
async def delete_me(body: PasswordConfirmIn, auth: CurrentAuth, db: DB) -> AcceptedOut:
    try:
        await delete_account(db, auth.user, password=body.password, confirm_email=body.email)
    except AuthError as exc:
        raise from_auth_error(exc) from exc
    return AcceptedOut(status="deleted", message="Hesabın ve tüm verilerin silindi.")


async def _watchlist(db: AsyncSession, user_id: int) -> list[str]:
    rows = await db.scalars(
        select(UserWatchlistItem.ticker)
        .where(UserWatchlistItem.user_id == user_id)
        .order_by(UserWatchlistItem.added_at, UserWatchlistItem.ticker)
    )
    return list(rows.all())


@router.get("/watchlist", response_model=WatchlistOut)
async def get_watchlist(auth: CurrentAuth, db: DB) -> WatchlistOut:
    return WatchlistOut(tickers=await _watchlist(db, auth.user.id))


@router.put("/watchlist", response_model=WatchlistOut)
async def replace_watchlist(body: WatchlistIn, auth: CurrentAuth, db: DB) -> WatchlistOut:
    """Listeyi verilenle degistirir; ayni govdeyle tekrar cagrilmasi etkisizdir."""
    user_id = auth.user.id
    tickers = normalize_tickers(body.tickers)
    await db.execute(
        delete(UserWatchlistItem).where(
            UserWatchlistItem.user_id == user_id, UserWatchlistItem.ticker.not_in(tickers)
        )
    )
    existing = set(await _watchlist(db, user_id))
    db.add_all(
        UserWatchlistItem(user_id=user_id, ticker=ticker)
        for ticker in tickers
        if ticker not in existing
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # es zamanli ayni istek; mevcut liste doner
    return WatchlistOut(tickers=await _watchlist(db, user_id))


async def _identities(db: AsyncSession, user_id: int) -> list[UserIdentity]:
    rows = await db.scalars(
        select(UserIdentity).where(UserIdentity.user_id == user_id).order_by(UserIdentity.id)
    )
    return list(rows.all())


@router.get("/identities", response_model=list[IdentityOut])
async def list_identities(auth: CurrentAuth, db: DB) -> list[UserIdentity]:
    return await _identities(db, auth.user.id)


@router.post("/identities/google", response_model=list[IdentityOut])
async def link_google(body: GoogleCodeIn, auth: CurrentAuth, db: DB) -> list[UserIdentity]:
    settings = get_settings()
    if not google.google_enabled(settings):
        raise HTTPException(
            status_code=404,
            detail={"code": "google_disabled", "message": "Google ile giriş etkin değil."},
        )
    try:
        profile = await google.exchange_code(
            settings, code=body.code, code_verifier=body.code_verifier, nonce=body.nonce
        )
        await google.link(db, auth.user, profile)
    except AuthError as exc:
        raise from_auth_error(exc) from exc
    return await _identities(db, auth.user.id)


@router.delete("/identities/google", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_google(auth: CurrentAuth, db: DB) -> Response:
    try:
        removed = await google.unlink(db, auth.user)
    except AuthError as exc:
        raise from_auth_error(exc) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Bağlı Google hesabı yok")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
