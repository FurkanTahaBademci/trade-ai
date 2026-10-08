"""Persisted provider backoff derived from recorded quota failures."""

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import LlmEvaluation

QUOTA_MARKERS = ("rate_limit", "rate limit", "resource_exhausted", "quota exceeded")


def quota_pause(message: str, failed_at: datetime, model: str) -> dict | None:
    lowered = message.lower()
    if not any(marker in lowered for marker in QUOTA_MARKERS):
        return None
    failed_at = failed_at.replace(tzinfo=UTC) if failed_at.tzinfo is None else failed_at
    daily = any(marker in lowered for marker in ("per day", "perday", "daily", "rpd"))
    if daily:
        # https://ai.google.dev/gemini-api/docs/rate-limits: RPD resets at midnight PT.
        pacific = failed_at.astimezone(ZoneInfo("America/Los_Angeles"))
        until = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        retry = re.search(r"retry (?:in|after)\s+(\d+(?:\.\d+)?)s", lowered)
        seconds = max(60, min(3600, float(retry[1]))) if retry else 300
        until = failed_at + timedelta(seconds=seconds)
    return {"reason": "daily_quota" if daily else "rate_limit", "model": model,
            "retry_at": until.astimezone(UTC).isoformat()}


async def get_provider_pause(
    session: AsyncSession, settings: Settings, *, now: datetime | None = None,
) -> dict | None:
    """Survive worker restarts without another paid request or a new persistence schema.

    Scope to the current API/models. A later successful evaluation of the same
    model clears an earlier failure (e.g. after a quota upgrade).
    """
    now = now or datetime.now(UTC)
    pauses = []
    for model in {settings.gemini_model_tier1, settings.gemini_model_tier2}:
        record = await session.scalar(
            select(LlmEvaluation).where(
                LlmEvaluation.model == model,
                LlmEvaluation.api_mode == settings.gemini_api_mode,
                LlmEvaluation.status == "failed",
                LlmEvaluation.completed_at >= now - timedelta(hours=26),
                or_(*(LlmEvaluation.error_text.ilike(f"%{marker}%") for marker in QUOTA_MARKERS)),
            ).order_by(LlmEvaluation.completed_at.desc(), LlmEvaluation.id.desc()).limit(1)
        )
        if record is None:
            continue
        pause = quota_pause(record.error_text or "", record.completed_at, model)
        if pause is None or datetime.fromisoformat(pause["retry_at"]) <= now:
            continue
        recovered = await session.scalar(select(LlmEvaluation.id).where(
            LlmEvaluation.model == model,
            LlmEvaluation.api_mode == settings.gemini_api_mode,
            LlmEvaluation.status == "succeeded",
            LlmEvaluation.completed_at > record.completed_at,
        ).limit(1))
        if recovered is None:
            pauses.append(pause)
    return max(pauses, key=lambda pause: pause["retry_at"]) if pauses else None
