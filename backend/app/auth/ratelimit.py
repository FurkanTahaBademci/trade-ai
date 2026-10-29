"""Hesap uclari icin Redis sabit pencere sayaclari.

Web birden cok surecle calistigi icin sayaclar Redis'te tutulur. Anahtarlarda
e-posta ve IP duz metin degil ozet olarak durur. Redis'e ulasilamazsa istek
engellenmez: hiz siniri bir savunma katmanidir, girisi kilitlememeli.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import structlog
from redis.exceptions import RedisError

from app.core.redis import get_redis

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Limit:
    name: str
    max_hits: int
    window_seconds: int


LOGIN_FAILURES_PER_IP = Limit("login_ip", 20, 15 * 60)
LOGIN_FAILURES_PER_EMAIL = Limit("login_email", 8, 15 * 60)
REGISTER_PER_IP = Limit("register_ip", 5, 60 * 60)
MAIL_PER_IP = Limit("mail_ip", 10, 60 * 60)
MAIL_PER_EMAIL = Limit("mail_email", 5, 60 * 60)
TOKEN_FAILURES_PER_IP = Limit("token_ip", 20, 15 * 60)


def _key(limit: Limit, subject: str) -> str:
    digest = hashlib.sha256(subject.encode()).hexdigest()[:32]
    return f"ratelimit:{limit.name}:{digest}"


async def is_limited(limit: Limit, subject: str) -> bool:
    try:
        count = await get_redis().get(_key(limit, subject))
    except RedisError as exc:
        logger.warning("ratelimit_unavailable", limit=limit.name, error=str(exc))
        return False
    return int(count or 0) >= limit.max_hits


async def hit(limit: Limit, subject: str) -> None:
    key = _key(limit, subject)
    try:
        redis = get_redis()
        if await redis.incr(key) == 1:
            await redis.expire(key, limit.window_seconds)
    except RedisError as exc:
        logger.warning("ratelimit_unavailable", limit=limit.name, error=str(exc))


async def take(limit: Limit, subject: str) -> bool:
    """Sinir dolmadiysa bir hak harcar ve True doner."""
    if await is_limited(limit, subject):
        return False
    await hit(limit, subject)
    return True
