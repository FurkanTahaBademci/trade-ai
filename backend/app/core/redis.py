"""Redis baglanti yardimcisi.

Tek bir baglanti havuzu; hem API hem worker ayni fonksiyonu kullanir.
Dedup setleri, rate-limit sayaclari ve dashboard pub/sub icin kullanilir.
"""

from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def ping_redis() -> bool:
    redis = get_redis()
    return await redis.ping()
