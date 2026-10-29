"""Kullanicinin bildirim tercihleri ve Telegram baglantisi.

Baglama: `POST /telegram/link` tek kullanimlik kodlu bir t.me baglantisi verir;
kullanici bot'a yazinca worker (dakikada bir) ya da `POST /telegram/check`
mesaji isler ve sohbeti hesaba baglar.
"""

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.personal import (
    create_link,
    get_pref,
    poll_telegram,
    send_test_message,
    telegram_ready,
)
from app.auth import ratelimit
from app.auth.deps import CurrentAuth
from app.core.config import get_settings
from app.core.db import get_db
from app.core.dynamic_settings import resolve_settings
from app.core.redis import get_redis
from app.mail.sender import smtp_configured
from app.models import UserAlertPref
from app.schemas.auth import AcceptedOut

router = APIRouter(prefix="/api/me/alerts", tags=["my-alerts"])
DB = Annotated[AsyncSession, Depends(get_db)]


class AlertPrefOut(BaseModel):
    available: bool
    telegram_available: bool
    email_available: bool
    telegram_linked: bool
    telegram_username: str | None
    telegram_linked_at: datetime | None
    telegram_instant: bool
    telegram_digest: bool
    email_digest: bool
    last_digest_on: date | None


class AlertPrefUpdate(BaseModel):
    telegram_instant: bool
    telegram_digest: bool
    email_digest: bool


class TelegramLinkOut(BaseModel):
    url: str
    expires_at: datetime


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


TOO_MANY = (429, "rate_limited", "Çok fazla deneme yapıldı. Biraz sonra tekrar dene.")
TELEGRAM_UNAVAILABLE = (
    503,
    "telegram_unavailable",
    "Telegram bildirimleri şu an kullanılamıyor. Daha sonra tekrar dene.",
)


async def _out(pref: UserAlertPref | None) -> AlertPrefOut:
    settings = await resolve_settings()
    base = get_settings()
    return AlertPrefOut(
        available=settings.user_alerts_enabled,
        telegram_available=telegram_ready(settings),
        # Gelistirmede e-posta log'a yazilir; production'da SMTP gerekir.
        email_available=settings.user_alerts_enabled
        and (smtp_configured(base) or base.environment.lower() != "production"),
        telegram_linked=bool(pref and pref.telegram_chat_id),
        telegram_username=pref.telegram_username if pref and pref.telegram_chat_id else None,
        telegram_linked_at=pref.telegram_linked_at if pref and pref.telegram_chat_id else None,
        telegram_instant=pref.telegram_instant if pref else True,
        telegram_digest=pref.telegram_digest if pref else True,
        email_digest=pref.email_digest if pref else False,
        last_digest_on=pref.last_digest_on if pref else None,
    )


@router.get("", response_model=AlertPrefOut)
async def my_alerts(auth: CurrentAuth, db: DB) -> AlertPrefOut:
    return await _out(await get_pref(db, auth.user.id))


@router.put("", response_model=AlertPrefOut)
async def update_my_alerts(body: AlertPrefUpdate, auth: CurrentAuth, db: DB) -> AlertPrefOut:
    pref = await get_pref(db, auth.user.id, create=True)
    assert pref is not None
    pref.telegram_instant = body.telegram_instant
    pref.telegram_digest = body.telegram_digest
    pref.email_digest = body.email_digest
    await db.commit()
    return await _out(pref)


@router.post("/telegram/link", response_model=TelegramLinkOut)
async def telegram_link(auth: CurrentAuth, db: DB) -> TelegramLinkOut:
    if not await ratelimit.take(ratelimit.TELEGRAM_LINK_PER_USER, str(auth.user.id)):
        raise _error(*TOO_MANY)
    async with httpx.AsyncClient(timeout=10) as client:
        link = await create_link(
            db, auth.user, settings=await resolve_settings(), redis=get_redis(), client=client
        )
    if link is None:
        raise _error(*TELEGRAM_UNAVAILABLE)
    return TelegramLinkOut(url=link[0], expires_at=link[1])


@router.post("/telegram/check", response_model=AlertPrefOut)
async def telegram_check(auth: CurrentAuth, db: DB) -> AlertPrefOut:
    """Bot'a gelen mesajlari hemen isler; kullanici worker'in sirasini beklemez."""
    if not await ratelimit.take(ratelimit.TELEGRAM_CHECK_PER_USER, str(auth.user.id)):
        raise _error(*TOO_MANY)

    @asynccontextmanager
    async def request_session():
        yield db

    async with httpx.AsyncClient(timeout=10) as client:
        await poll_telegram(
            request_session, settings=await resolve_settings(), redis=get_redis(), client=client
        )
    pref = await get_pref(db, auth.user.id)
    if pref is not None:
        await db.refresh(pref)
    return await _out(pref)


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_unlink(auth: CurrentAuth, db: DB) -> Response:
    pref = await get_pref(db, auth.user.id)
    if pref is not None and pref.telegram_chat_id:
        pref.telegram_chat_id = None
        pref.telegram_username = None
        pref.telegram_linked_at = None
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=AcceptedOut)
async def telegram_test(auth: CurrentAuth, db: DB) -> AcceptedOut:
    pref = await get_pref(db, auth.user.id)
    if pref is None or not pref.telegram_chat_id:
        raise _error(409, "not_linked", "Önce Telegram hesabını bağla.")
    if not await ratelimit.take(ratelimit.ALERT_TEST_PER_USER, str(auth.user.id)):
        raise _error(*TOO_MANY)
    async with httpx.AsyncClient(timeout=10) as client:
        sent = await send_test_message(pref, settings=await resolve_settings(), client=client)
    if not sent:
        raise _error(*TELEGRAM_UNAVAILABLE)
    return AcceptedOut(status="sent", message="Test mesajı Telegram'a gönderildi.")
