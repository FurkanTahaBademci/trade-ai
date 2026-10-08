"""Bildirim kanallari: Telegram sendMessage ve genel JSON webhook.

Kanal fonksiyonlari asla exception firlatmaz; sonucu `{"channel", "ok", ...}`
sozlugu olarak dondurur. Hata mesajlarindan bot token'i temizlenir (httpx
istisnalari URL'yi, yani token'i icerir).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"
SEVERITY_ICONS = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}


@dataclass(frozen=True)
class AlertMessage:
    event_type: str
    title: str
    message: str
    severity: str = "info"
    details: dict[str, Any] = field(default_factory=dict)


def _scrub(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text[:300]


def format_telegram_text(alert: AlertMessage) -> str:
    icon = SEVERITY_ICONS.get(alert.severity, "")
    return f"{icon} {alert.title}\n{alert.message}".strip()


def build_webhook_payload(alert: AlertMessage) -> dict[str, Any]:
    return {
        "source": "trade-ai",
        "event_type": alert.event_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "details": alert.details,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def configured_channels(settings: Settings) -> list[str]:
    channels: list[str] = []
    if settings.alerts_telegram_bot_token and settings.alerts_telegram_chat_id:
        channels.append("telegram")
    if settings.alerts_webhook_url:
        channels.append("webhook")
    return channels


async def send_telegram(
    alert: AlertMessage, settings: Settings, client: httpx.AsyncClient
) -> dict[str, Any]:
    token = settings.alerts_telegram_bot_token
    try:
        response = await client.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": settings.alerts_telegram_chat_id,
                "text": format_telegram_text(alert),
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        return {"channel": "telegram", "ok": True}
    except Exception as exc:  # noqa: BLE001 - bildirim hatasi asil isi durdurmamali
        error = _scrub(str(exc), token, settings.alerts_telegram_chat_id)
        logger.error("alert_channel_failed", channel="telegram", error=error)
        return {"channel": "telegram", "ok": False, "error": error}


async def send_webhook(
    alert: AlertMessage, settings: Settings, client: httpx.AsyncClient
) -> dict[str, Any]:
    url = settings.alerts_webhook_url
    try:
        response = await client.post(url, json=build_webhook_payload(alert))
        response.raise_for_status()
        return {"channel": "webhook", "ok": True}
    except Exception as exc:  # noqa: BLE001 - bildirim hatasi asil isi durdurmamali
        error = _scrub(str(exc), url)
        logger.error("alert_channel_failed", channel="webhook", error=error)
        return {"channel": "webhook", "ok": False, "error": error}


async def deliver(
    alert: AlertMessage, settings: Settings, client: httpx.AsyncClient
) -> list[dict[str, Any]]:
    """Yapilandirilmis tum kanallara gonderir; kanal basina sonuc listesi dondurur."""
    results: list[dict[str, Any]] = []
    for channel in configured_channels(settings):
        sender = send_telegram if channel == "telegram" else send_webhook
        results.append(await sender(alert, settings, client))
    return results
