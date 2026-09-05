"""Saglik kontrolu endpoint'leri.

/health          -> hizli, sadece process ayakta mi (Docker HEALTHCHECK icin)
/health/detailed -> DB + Redis baglantisini gercekten test eder, ayrica
                     Faz 2+'da her collector'in son basarili calisma
                     zamanini burada raporlayacagiz (bkz. plan Faz 10).
"""

import structlog
from fastapi import APIRouter

from app.core.db import ping_db
from app.core.redis import ping_redis

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed() -> dict:
    result: dict = {"db": "unknown", "redis": "unknown"}

    try:
        await ping_db()
        result["db"] = "ok"
    except Exception as exc:  # noqa: BLE001 - saglik kontrolunde genis yakalama istenir
        logger.error("db_ping_failed", error=str(exc))
        result["db"] = f"error: {exc}"

    try:
        await ping_redis()
        result["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("redis_ping_failed", error=str(exc))
        result["redis"] = f"error: {exc}"

    result["status"] = "ok" if result["db"] == "ok" and result["redis"] == "ok" else "degraded"
    return result
