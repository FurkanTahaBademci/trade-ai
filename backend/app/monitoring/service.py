"""Collector tazeligi, worker heartbeat'i ve idempotent webhook alarmlari."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

# Sik akan kaynaklarda kisa, is gunu bazli kaynaklarda hafta sonunu tolere eden
# esikler kullanilir. Degerler saniye cinsindendir.
COLLECTOR_POLICIES: dict[str, tuple[str, int]] = {
    "kap": ("KAP bildirimleri", 20 * 60),
    "news": ("Haber akisi", 20 * 60),
    "instruments": ("Hisse evreni", 72 * 60 * 60),
    "prices": ("EOD fiyatlari", 80 * 60 * 60),
    "fundamentals": ("Temel analiz", 80 * 60 * 60),
    "analysts": ("Analist gorusleri", 80 * 60 * 60),
    "institutional_reports": ("Kurum raporlari", 80 * 60 * 60),
    "fund_flows": ("TEFAS fon akimi", 96 * 60 * 60),
    "tcmb_policy": ("TCMB faiz kararlari", 72 * 60 * 60),
}
WORKER_MAX_AGE_SECONDS = 10 * 60


def parse_event_time(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.split(" | ", 1)[0].strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def evaluate_freshness(
    *,
    last_success: str | None,
    last_error: str | None,
    max_age_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    success_at = parse_event_time(last_success)
    error_at = parse_event_time(last_error)

    if error_at is not None and (success_at is None or error_at > success_at):
        state = "error"
        age_seconds = max(0, int((current - error_at).total_seconds()))
    elif success_at is None:
        state = "pending"
        age_seconds = None
    else:
        age_seconds = max(0, int((current - success_at).total_seconds()))
        state = "stale" if age_seconds > max_age_seconds else "healthy"

    return {
        "state": state,
        "last_success": success_at.isoformat() if success_at else None,
        "last_error_at": error_at.isoformat() if error_at else None,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
    }


async def get_monitoring_report(
    redis: Redis | None = None, *, now: datetime | None = None
) -> dict[str, Any]:
    client = redis or get_redis()
    names = list(COLLECTOR_POLICIES)
    keys = [
        key
        for name in names
        for key in (
            f"collector:{name}:last_success",
            f"collector:{name}:last_error",
        )
    ]
    values = await client.mget([*keys, "worker:last_heartbeat"])
    collectors: dict[str, dict[str, Any]] = {}

    for index, name in enumerate(names):
        label, max_age = COLLECTOR_POLICIES[name]
        status = evaluate_freshness(
            last_success=values[index * 2],
            last_error=values[index * 2 + 1],
            max_age_seconds=max_age,
            now=now,
        )
        collectors[name] = {"name": name, "label": label, **status}

    worker_status = evaluate_freshness(
        last_success=values[-1],
        last_error=None,
        max_age_seconds=WORKER_MAX_AGE_SECONDS,
        now=now,
    )
    worker = {"name": "worker", "label": "ARQ worker", **worker_status}
    components = [*collectors.values(), worker]
    problem_count = sum(item["state"] in {"error", "stale"} for item in components)
    pending_count = sum(item["state"] == "pending" for item in components)
    status = "degraded" if problem_count else "pending" if pending_count else "ok"
    return {
        "status": status,
        "problem_count": problem_count,
        "pending_count": pending_count,
        "worker": worker,
        "collectors": collectors,
        "checked_at": (now or datetime.now(UTC)).astimezone(UTC).isoformat(),
    }


async def send_webhook_alert(
    *,
    event_type: str,
    title: str,
    message: str,
    severity: str = "warning",
    details: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    redis: Redis | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.n8n_webhook_url:
        return {"enabled": False, "delivered": False, "reason": "N8N_WEBHOOK_URL bos"}

    redis_client = redis or get_redis()
    fingerprint = dedupe_key or f"{event_type}|{title}|{message}"
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    cooldown_key = f"alert:cooldown:{digest}"
    acquired = await redis_client.set(
        cooldown_key,
        "1",
        ex=settings.monitoring_alert_cooldown_seconds,
        nx=True,
    )
    if not acquired:
        return {"enabled": True, "delivered": False, "reason": "deduplicated"}

    payload = {
        "source": "trade-ai",
        "event_type": event_type,
        "severity": severity,
        "title": title,
        "message": message,
        "details": details or {},
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=10)
    try:
        response = await http_client.post(settings.n8n_webhook_url, json=payload)
        response.raise_for_status()
        logger.info("monitoring_alert_delivered", event_type=event_type, severity=severity)
        return {"enabled": True, "delivered": True}
    except Exception as exc:  # noqa: BLE001 - alarm hatasi asil isi durdurmamali
        await redis_client.delete(cooldown_key)
        logger.error("monitoring_alert_failed", event_type=event_type, error=str(exc))
        return {"enabled": True, "delivered": False, "reason": str(exc)}
    finally:
        if owns_client:
            await http_client.aclose()


async def monitor_system(ctx: dict) -> dict[str, Any]:
    """Bayat/hata durumundaki bilesenleri N8N'e, cooldown ile bir kez bildirir."""
    report = await get_monitoring_report()
    problems = [
        item
        for item in [*report["collectors"].values(), report["worker"]]
        if item["state"] in {"error", "stale"}
    ]
    delivered = 0
    for item in problems:
        result = await send_webhook_alert(
            event_type="component_unhealthy",
            severity="error" if item["state"] == "error" else "warning",
            title=f"{item['label']} {item['state']}",
            message=f"{item['name']} bileseni beklenen tazelik sinirinin disinda.",
            details=item,
            dedupe_key=f"component_unhealthy:{item['name']}:{item['state']}",
        )
        delivered += int(result.get("delivered", False))
    return {
        "status": report["status"],
        "problems": len(problems),
        "alerts_delivered": delivered,
    }
