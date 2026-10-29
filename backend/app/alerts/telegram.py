"""Kullanici sohbetleri icin Telegram Bot API cagrilari.

Yoneticinin bildirim bot'u (`alerts_telegram_bot_token`) kullanilir. Bot'a
gelen mesajlar webhook yerine worker'dan kisa sorguyla (getUpdates) okunur:
API internete kapali oldugu icin disaridan istek almak gerekmez. Bot'ta webhook
tanimliysa Telegram getUpdates'e 409 doner; baglama o durumda calismaz.

Fonksiyonlar exception firlatmaz; hata metinlerinden token temizlenir.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis

from app.alerts.channels import TELEGRAM_API, _scrub

logger = structlog.get_logger(__name__)

BOT_USERNAME_TTL_SECONDS = 24 * 60 * 60
# Telegram tek mesajda 4096 karakter kabul eder.
MAX_TEXT_LENGTH = 4000


@dataclass(frozen=True)
class SendResult:
    ok: bool
    # Kullanici bot'u engelledi ya da sohbet yok: baglanti kaldirilmali.
    blocked: bool = False
    error: str | None = None


def _url(token: str, method: str) -> str:
    return f"{TELEGRAM_API}/bot{token}/{method}"


def _description(response: httpx.Response) -> str:
    try:
        return str(response.json().get("description") or "")[:200]
    except ValueError:
        return ""


async def send_text(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> SendResult:
    try:
        response = await client.post(
            _url(token, "sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text[:MAX_TEXT_LENGTH],
                "disable_web_page_preview": True,
            },
        )
    except httpx.HTTPError as exc:
        return SendResult(ok=False, error=_scrub(str(exc), token))
    if response.status_code == 200:
        return SendResult(ok=True)
    description = _description(response)
    blocked = response.status_code == 403 or "chat not found" in description.lower()
    return SendResult(
        ok=False, blocked=blocked, error=description or f"HTTP {response.status_code}"
    )


async def bot_username(client: httpx.AsyncClient, token: str, redis: Redis) -> str | None:
    """Derin baglanti (t.me/<bot>?start=...) icin bot kullanici adi; bir gun onbellekte."""
    key = f"telegram:bot_username:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    try:
        cached = await redis.get(key)
    except Exception:  # noqa: BLE001 - Redis yoksa dogrudan sorulur
        cached = None
    if cached:
        return cached
    try:
        response = await client.post(_url(token, "getMe"))
        username = (
            response.json().get("result", {}).get("username") if response.is_success else None
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("telegram_get_me_failed", error=_scrub(str(exc), token))
        return None
    if not username:
        logger.warning("telegram_get_me_failed", status=response.status_code)
        return None
    try:
        await redis.set(key, username, ex=BOT_USERNAME_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 - onbellek yazilamasa da ad kullanilir
        logger.warning("telegram_bot_username_cache_failed", error=str(exc)[:200])
    return username


async def get_updates(
    client: httpx.AsyncClient, token: str, offset: int | None
) -> tuple[list[dict[str, Any]], str | None]:
    """Bekleyen mesajlari bekletmeden alir. Hata varsa (bos liste, hata kodu) doner."""
    payload: dict[str, Any] = {"timeout": 0, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = offset
    try:
        response = await client.post(_url(token, "getUpdates"), json=payload)
    except httpx.HTTPError as exc:
        return [], _scrub(str(exc), token)
    if response.status_code == 409:
        return [], "conflict"
    if not response.is_success:
        return [], _description(response) or f"HTTP {response.status_code}"
    try:
        result = response.json().get("result")
    except ValueError:
        return [], "invalid_response"
    return (result if isinstance(result, list) else []), None
