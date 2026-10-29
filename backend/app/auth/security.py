"""Parola ozeti, rastgele token ve e-posta bicimi (DB'siz, saf yardimcilar)."""

from __future__ import annotations

import asyncio
import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
EMAIL_MAX_LENGTH = 254
# Karistirilmayan harf/rakamlar (0/O, 1/I yok); davet kodu elle yazilabilsin.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# argon2id, RFC 9106 dusuk bellek profili (64 MiB, t=3, p=4).
_hasher = PasswordHasher()
_dummy_hash: str | None = None
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(raw: str) -> str | None:
    email = raw.strip().lower()
    if len(email) > EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.match(email):
        return None
    return email


def password_problem(password: str) -> str | None:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Parola en az {PASSWORD_MIN_LENGTH} karakter olmalı."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Parola en fazla {PASSWORD_MAX_LENGTH} karakter olabilir."
    if len(set(password)) < 4:
        return "Parola çok tahmin edilebilir; farklı karakterler kullan."
    return None


async def hash_password(password: str) -> str:
    # Ozet ~50 ms CPU; event loop'u bekletmesin.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    global _dummy_hash
    if not password_hash:
        # Kayitli olmayan e-postada da ayni sure harcanir (zamanlama ile
        # hesap varligi anlasilmasin).
        if _dummy_hash is None:
            _dummy_hash = await hash_password(secrets.token_hex(16))
        password_hash = _dummy_hash
        password = ""
    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password) and bool(password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """(kullaniciya verilecek ham token, DB'de saklanacak ozet)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def new_invite_code() -> str:
    groups = ["".join(secrets.choice(INVITE_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


def normalize_invite_code(raw: str) -> str:
    return raw.strip().upper()
