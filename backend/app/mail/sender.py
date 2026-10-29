"""SMTP ile duz metin e-posta gonderimi ve worker kuyruguna ekleme.

API istegi e-postayi beklemez: `enqueue_mail` isi Redis kuyruguna birakir,
worker `send_email` isiyle gonderir. SMTP tanimli degilse gelistirmede icerik
log'a yazilir (dogrulama baglantisi oradan acilabilir); production'da yalniz
uyari loglanir, baglanti log'a dusmez.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import structlog
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    text: str


def smtp_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_host and settings.mail_from)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def build_message(settings: Settings, mail: OutgoingMail) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message["Date"] = formatdate(localtime=False)
    domain = parseaddr(settings.mail_from)[1].partition("@")[2] or None
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(mail.text)
    return message


def _deliver(settings: Settings, mail: OutgoingMail) -> None:
    message = build_message(settings, mail)
    context = ssl.create_default_context()
    security = settings.smtp_security.lower()
    if security == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=20, context=context
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with client:
        if security == "starttls":
            client.starttls(context=context)
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_mail(mail: OutgoingMail, settings: Settings | None = None) -> str:
    """Gonderildiyse "sent", gelistirmede "logged", SMTP'siz production'da "skipped"."""
    settings = settings or get_settings()
    if not smtp_configured(settings):
        if settings.environment.lower() != "production":
            logger.info("mail_not_sent_dev", to=mail.to, subject=mail.subject, text=mail.text)
            return "logged"
        logger.warning("mail_not_configured", to=mask_email(mail.to), subject=mail.subject)
        return "skipped"
    await asyncio.to_thread(_deliver, settings, mail)
    logger.info("mail_sent", to=mask_email(mail.to), subject=mail.subject)
    return "sent"


async def enqueue_mail(mail: OutgoingMail) -> bool:
    """E-postayi worker kuyruguna ekler; Redis yoksa istegi bozmadan False doner."""
    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    except Exception as exc:  # noqa: BLE001 - kullanici yeniden gonderimi isteyebilir
        logger.error("mail_enqueue_failed", subject=mail.subject, error=str(exc))
        return False
    try:
        await pool.enqueue_job("send_email", mail.to, mail.subject, mail.text)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("mail_enqueue_failed", subject=mail.subject, error=str(exc))
        return False
    finally:
        await pool.aclose()
