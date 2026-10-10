"""Alarm olaylari: skor etiketi degisimi, sistem sagligi, yuksek skorlu sinyal.

Idempotency: her olay icin Redis'te `alerts:sent:<sha256>` anahtari `SET NX EX`
ile alinir; anahtar zaten varsa olay tekrar gonderilmez. Tum kanallar basarisiz
olursa anahtar silinir ki bir sonraki degerlendirmede yeniden denensin.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.channels import AlertMessage, configured_channels, deliver
from app.core.config import Settings
from app.core.dynamic_settings import resolve_settings
from app.core.redis import get_redis
from app.models import CompositeSignalSnapshot, PaperPortfolio, PaperPosition, WatchlistItem
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

logger = structlog.get_logger(__name__)

SENT_KEY_PREFIX = "alerts:sent:"
LABEL_STATE_KEY = "alerts:label_state"
EVENT_TTL_SECONDS = 7 * 24 * 60 * 60
LABEL_TEXT = {
    "VERY_POSITIVE": "Çok olumlu",
    "POSITIVE": "Olumlu",
    "NEUTRAL": "Nötr",
    "NEGATIVE": "Olumsuz",
    "VERY_NEGATIVE": "Çok olumsuz",
}


def parse_watch_tickers(raw: str) -> set[str]:
    return {item.strip().upper() for item in raw.replace(";", ",").split(",") if item.strip()}


def detect_label_changes(
    previous: dict[str, str], current: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Onceki etiketi bilinen ve degisen hisseleri dondurur (ilk gozlem alarm degildir)."""
    changes = []
    for ticker, row in sorted(current.items()):
        before = previous.get(ticker)
        if before and before != row["label"]:
            changes.append({**row, "ticker": ticker, "from": before, "to": row["label"]})
    return changes


def label_change_alert(change: dict[str, Any]) -> AlertMessage:
    old = LABEL_TEXT.get(change["from"], change["from"])
    new = LABEL_TEXT.get(change["to"], change["to"])
    return AlertMessage(
        event_type="signal_label_changed",
        severity="info",
        title=f"{change['ticker']} skor etiketi değişti: {old} → {new}",
        message=f"Bileşik skor {change['score']:.1f}/100 ({change['as_of_date']}).",
        details={k: str(v) for k, v in change.items()},
    )


def high_score_alert(row: dict[str, Any]) -> AlertMessage:
    return AlertMessage(
        event_type="high_score_signal",
        severity="info",
        title=f"{row['ticker']} çok yüksek skor: {row['score']:.1f}/100",
        message=f"Etiket: {LABEL_TEXT.get(row['label'], row['label'])} ({row['as_of_date']}).",
        details={k: str(v) for k, v in row.items()},
    )


def _digest(dedupe_key: str) -> str:
    return hashlib.sha256(dedupe_key.encode()).hexdigest()


async def dispatch_alert(
    alert: AlertMessage,
    *,
    dedupe_key: str,
    settings: Settings,
    redis: Redis,
    client: httpx.AsyncClient,
    ttl_seconds: int = EVENT_TTL_SECONDS,
) -> dict[str, Any]:
    """Olayi en fazla bir kez gonderir. Asla exception firlatmaz."""
    if not settings.alerts_enabled or not configured_channels(settings):
        return {"delivered": False, "reason": "disabled"}
    key = f"{SENT_KEY_PREFIX}{_digest(dedupe_key)}"
    try:
        if not await redis.set(key, "1", ex=ttl_seconds, nx=True):
            return {"delivered": False, "reason": "deduplicated"}
        results = await deliver(alert, settings, client)
    except Exception as exc:  # noqa: BLE001 - alarm hatasi worker'i cokertmemeli
        logger.error("alert_dispatch_failed", event_type=alert.event_type, error=str(exc))
        return {"delivered": False, "reason": "error"}
    if not any(item["ok"] for item in results):
        try:
            await redis.delete(key)
        except Exception:  # noqa: BLE001
            logger.error("alert_dedupe_release_failed", event_type=alert.event_type)
        return {"delivered": False, "reason": "delivery_failed", "results": results}
    logger.info("alert_delivered", event_type=alert.event_type)
    return {"delivered": True, "results": results}


async def send_test_alert(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> list[dict[str, Any]]:
    """Dedupe ve 'etkin' bayragini atlayarak yapilandirilmis kanallara test mesaji yollar."""
    alert = AlertMessage(
        event_type="test",
        severity="info",
        title="trade-ai test bildirimi",
        message="Bildirim kanalı doğru yapılandırıldı.",
    )
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=10)
    try:
        return await deliver(alert, settings, http_client)
    finally:
        if owns_client:
            await http_client.aclose()


async def _load_scores(session: AsyncSession) -> tuple[date | None, dict[str, dict[str, Any]]]:
    as_of = await session.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION
        )
    )
    if as_of is None:
        return None, {}
    rows = (
        await session.scalars(
            select(CompositeSignalSnapshot).where(
                CompositeSignalSnapshot.as_of_date == as_of,
                CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
            )
        )
    ).all()
    return as_of, {
        row.ticker: {
            "label": row.signal_label,
            "score": float(row.composite_score),
            "as_of_date": as_of.isoformat(),
        }
        for row in rows
    }


async def _watched_tickers(session: AsyncSession, settings: Settings) -> set[str]:
    """Aktif paper pozisyonlari + web izleme listesi + ayarlardaki ek hisseler."""
    held = (
        await session.scalars(
            select(PaperPosition.ticker)
            .join(PaperPortfolio, PaperPortfolio.id == PaperPosition.portfolio_id)
            .where(PaperPortfolio.status == "ACTIVE")
        )
    ).all()
    listed = (await session.scalars(select(WatchlistItem.ticker))).all()
    return set(held) | set(listed) | parse_watch_tickers(settings.alerts_watch_tickers)


async def evaluate_signal_alerts(
    session: AsyncSession,
    *,
    settings: Settings,
    redis: Redis,
    client: httpx.AsyncClient,
) -> dict[str, int]:
    watched = await _watched_tickers(session, settings)
    as_of, scores = await _load_scores(session)
    stats = {"label_changes": 0, "high_scores": 0}
    if as_of is None:
        return stats

    watched_scores = {t: r for t, r in scores.items() if t in watched}
    previous = await redis.hgetall(LABEL_STATE_KEY)
    unsent: set[str] = set()
    for change in detect_label_changes(previous, watched_scores):
        result = await dispatch_alert(
            label_change_alert(change),
            dedupe_key=(
                f"label:{change['ticker']}:{change['from']}:{change['to']}:{change['as_of_date']}"
            ),
            settings=settings,
            redis=redis,
            client=client,
        )
        stats["label_changes"] += int(result["delivered"])
        if result.get("reason") in {"delivery_failed", "error"}:
            # Etiket durumu ilerletilmez; sonraki turda ayni degisim yeniden denenir.
            unsent.add(change["ticker"])
    state = {t: r["label"] for t, r in watched_scores.items() if t not in unsent}
    if state:
        await redis.hset(LABEL_STATE_KEY, mapping=state)

    for ticker, row in sorted(scores.items()):
        if row["score"] < settings.alerts_high_score_threshold:
            continue
        result = await dispatch_alert(
            high_score_alert({**row, "ticker": ticker}),
            dedupe_key=f"high_score:{ticker}:{row['as_of_date']}",
            settings=settings,
            redis=redis,
            client=client,
        )
        stats["high_scores"] += int(result["delivered"])
    return stats


async def evaluate_health_alerts(
    *,
    settings: Settings,
    redis: Redis,
    client: httpx.AsyncClient,
    report: dict[str, Any] | None = None,
) -> int:
    from app.monitoring.service import get_monitoring_report

    report = report or await get_monitoring_report(redis)
    delivered = 0
    for item in [*report["collectors"].values(), report["worker"]]:
        if item["state"] not in {"error", "stale"}:
            continue
        result = await dispatch_alert(
            AlertMessage(
                event_type="component_unhealthy",
                severity="error" if item["state"] == "error" else "warning",
                title=f"{item['label']} {item['state']}",
                message=f"{item['name']} bileşeni beklenen tazelik sınırının dışında.",
                details={k: str(v) for k, v in item.items()},
            ),
            dedupe_key=f"health:{item['name']}:{item['state']}",
            settings=settings,
            redis=redis,
            client=client,
            ttl_seconds=settings.monitoring_alert_cooldown_seconds,
        )
        delivered += int(result["delivered"])
    return delivered


async def evaluate_alerts(ctx: dict) -> dict[str, Any]:
    """ARQ cron girisi: tum olay turlerini degerlendirir, hicbir hatayi disari sizdirmaz."""
    from app.core.db import session_factory

    redis = get_redis()
    try:
        settings = await resolve_settings(redis=redis)
        if not settings.alerts_enabled or not configured_channels(settings):
            return {"enabled": False}
        async with httpx.AsyncClient(timeout=10) as client:
            health = await evaluate_health_alerts(settings=settings, redis=redis, client=client)
            async with session_factory() as session:
                signals = await evaluate_signal_alerts(
                    session, settings=settings, redis=redis, client=client
                )
        return {"enabled": True, "health": health, **signals}
    except Exception as exc:  # noqa: BLE001 - alarm degerlendirmesi worker'i cokertmemeli
        logger.error("alert_evaluation_failed", error=str(exc))
        return {"enabled": True, "error": str(exc)[:200]}
