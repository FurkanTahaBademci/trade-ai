"""Hesap e-postalarinin Turkce metinleri (duz metin)."""

from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import get_settings
from app.mail.sender import OutgoingMail

PRODUCT = "TradeAI"
FOOTER = (
    "\n\n—\n"
    f"{PRODUCT} · BIST piyasa araştırma terminali. Paper portföyler sanaldır, "
    "yatırım tavsiyesi değildir."
)
IGNORE_HINT = "\n\nBu e-postayı sen istemediysen dikkate alma; hesabında bir değişiklik olmaz."


def link(path: str, **params: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    query = f"?{urlencode(params)}" if params else ""
    return f"{base}{path}{query}"


def verification_mail(to: str, token: str) -> OutgoingMail:
    return OutgoingMail(
        to=to,
        subject=f"{PRODUCT} · E-posta adresini doğrula",
        text=(
            "Merhaba,\n\n"
            f"{PRODUCT} hesabını etkinleştirmek için aşağıdaki bağlantıyı aç:\n\n"
            f"{link('/eposta-dogrula', token=token)}\n\n"
            "Bağlantı 48 saat geçerlidir." + IGNORE_HINT + FOOTER
        ),
    )


def account_exists_mail(to: str) -> OutgoingMail:
    return OutgoingMail(
        to=to,
        subject=f"{PRODUCT} · Bu adresle zaten bir hesabın var",
        text=(
            "Merhaba,\n\n"
            "Bu e-posta adresiyle yeniden kayıt olunmaya çalışıldı, ama zaten bir "
            "hesabın var. Giriş yapabilir ya da parolanı sıfırlayabilirsin:\n\n"
            f"Giriş: {link('/giris')}\n"
            f"Parolamı unuttum: {link('/sifremi-unuttum')}" + IGNORE_HINT + FOOTER
        ),
    )


def password_reset_mail(to: str, token: str) -> OutgoingMail:
    return OutgoingMail(
        to=to,
        subject=f"{PRODUCT} · Parola sıfırlama",
        text=(
            "Merhaba,\n\n"
            "Parolanı sıfırlamak için aşağıdaki bağlantıyı aç:\n\n"
            f"{link('/sifre-sifirla', token=token)}\n\n"
            "Bağlantı 1 saat geçerlidir ve yalnız bir kez kullanılabilir." + IGNORE_HINT + FOOTER
        ),
    )


def password_changed_mail(to: str) -> OutgoingMail:
    return OutgoingMail(
        to=to,
        subject=f"{PRODUCT} · Parolan değiştirildi",
        text=(
            "Merhaba,\n\n"
            "Hesabının parolası az önce değiştirildi ve diğer cihazlardaki oturumlar "
            "kapatıldı.\n\n"
            "Bunu sen yapmadıysan hemen parolanı sıfırla:\n"
            f"{link('/sifremi-unuttum')}" + FOOTER
        ),
    )
