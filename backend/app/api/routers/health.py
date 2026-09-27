"""Saglik kontrolu endpoint'leri.

/health          -> hizli, sadece process ayakta mi (Docker HEALTHCHECK icin)
/health/detailed -> DB + Redis baglantisini gercekten test eder, ayrica
                     Faz 2+'da her collector'in son basarili calisma
                     zamanini burada raporlayacagiz (bkz. plan Faz 10).
"""

import asyncio

import structlog
from fastapi import APIRouter, Response

from app.core.db import ping_db
from app.core.redis import ping_redis
from app.monitoring.service import get_monitoring_report

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed() -> dict:
    result: dict = {"db": "unknown", "redis": "unknown", "monitoring": None}

    try:
        await asyncio.wait_for(ping_db(), timeout=2)
        result["db"] = "ok"
    except Exception as exc:  # noqa: BLE001 - saglik kontrolunde genis yakalama istenir
        logger.error("db_ping_failed", error=str(exc))
        result["db"] = "error"

    try:
        await asyncio.wait_for(ping_redis(), timeout=2)
        result["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("redis_ping_failed", error=str(exc))
        result["redis"] = "error"

    if result["redis"] == "ok":
        try:
            result["monitoring"] = await asyncio.wait_for(get_monitoring_report(), timeout=2)
        except Exception as exc:  # noqa: BLE001 - monitoring failure is not a Redis outage
            logger.error("monitoring_report_failed", error=str(exc))

    infrastructure_ok = result["db"] == "ok" and result["redis"] == "ok"
    monitoring_ok = result["monitoring"] and result["monitoring"]["status"] == "ok"
    result["status"] = "ok" if infrastructure_ok and monitoring_ok else "degraded"
    return result


@router.get("/health/ready")
async def health_ready(response: Response) -> dict:
    """Readiness depends on storage, not collector freshness or initial seeding."""
    checks = await asyncio.gather(
        asyncio.wait_for(ping_db(), timeout=2),
        asyncio.wait_for(ping_redis(), timeout=2),
        return_exceptions=True,
    )
    result = {
        name: "error" if isinstance(check, BaseException) else "ok"
        for name, check in zip(("db", "redis"), checks, strict=True)
    }
    ready = all(value == "ok" for value in result.values())
    response.status_code = 200 if ready else 503
    return {"status": "ok" if ready else "degraded", **result}
