"""Yapay Zeka Gunluk Piyasa Bulteni endpoint'i."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.models.llm_evaluation import LlmEvaluation
from app.models.macro import MonetaryPolicyDecision
from app.models.news import NewsArticle
from app.models.signal import CompositeSignalSnapshot
from app.signals.service import MODEL_VERSION

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = logging.getLogger(__name__)


@router.get("/briefing")
async def get_market_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Gunun gelismelerini, KAP aciklamalarini ve sektor beklentilerini ozetleyen AI Yonetici Bulteni."""
    now = datetime.now(UTC)
    local_now = now.astimezone(ZoneInfo("Europe/Istanbul"))
    date_str = local_now.date().isoformat()
    since = now - timedelta(hours=24)
    # Sabah 09:00 - 18:00 arasi "SABAH", aksam 18:00 sonrasi "AKŞAM"
    session_name = "SABAH" if 9 <= local_now.hour < 18 else "AKŞAM"
    cache_key = f"ai:briefing:v2:{date_str}:{session_name}"

    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Briefing cache read failed: %s", exc)

    # 1. En son yuksek etkili KAP degerlendirmeleri
    kap_eval_stmt = (
        select(LlmEvaluation)
        .where(
            LlmEvaluation.source_type == "kap",
            LlmEvaluation.status == "succeeded",
            LlmEvaluation.completed_at >= since,
            LlmEvaluation.impact_score.is_not(None),
        )
        .order_by(desc(LlmEvaluation.impact_score), desc(LlmEvaluation.created_at))
        .limit(5)
    )
    kap_evals = (await db.scalars(kap_eval_stmt)).all()

    # 2. En son haberler
    news_stmt = (
        select(NewsArticle)
        .where(NewsArticle.published_at >= since, NewsArticle.published_at <= now)
        .order_by(desc(NewsArticle.published_at))
        .limit(6)
    )
    news_items = (await db.scalars(news_stmt)).all()

    # 3. TCMB son politika faizi
    macro_stmt = (
        select(MonetaryPolicyDecision)
        .where(
            MonetaryPolicyDecision.status == "PUBLISHED",
            MonetaryPolicyDecision.decision_date <= local_now.date(),
        )
        .order_by(desc(MonetaryPolicyDecision.decision_date))
        .limit(1)
    )
    latest_macro = (await db.scalars(macro_stmt)).first()

    # Use the full latest snapshot for sentiment, not merely the top five rows.
    latest_signal_date = (
        select(func.max(CompositeSignalSnapshot.as_of_date))
        .where(CompositeSignalSnapshot.model_version == MODEL_VERSION)
        .scalar_subquery()
    )
    pos_signals_stmt = (
        select(CompositeSignalSnapshot)
        .where(
            CompositeSignalSnapshot.as_of_date == latest_signal_date,
            CompositeSignalSnapshot.model_version == MODEL_VERSION,
            CompositeSignalSnapshot.computed_at >= since,
        )
        .order_by(desc(CompositeSignalSnapshot.composite_score))
    )
    top_signals = (await db.scalars(pos_signals_stmt)).all()

    # Deterministik / akilli sentez
    top_tickers = [s.ticker for s in top_signals[:3]]
    catalysts = []

    for ev in kap_evals[:3]:
        sentiment = ev.sentiment_score or 0
        impact_str = "POSITIVE" if sentiment > 0 else "NEGATIVE" if sentiment < 0 else "NEUTRAL"
        catalysts.append(
            {
                "title": ev.event_type or "KAP Bildirimi",
                "category": "KAP",
                "impact": impact_str,
                "tickers": ev.ticker_codes or [],
                "description": ev.summary or "Önemli şirket bildirimi kaydedildi.",
            }
        )

    for n in news_items[:2]:
        catalysts.append(
            {
                "title": n.title,
                "category": "HABER",
                "impact": "NEUTRAL",
                "tickers": n.ticker_codes or [],
                "description": f"{n.source.upper()} kaynaklı piyasa haberi.",
            }
        )

    rate_text = (
        f"Son kayıtlı TCMB politika faizi %{latest_macro.policy_rate:.2f} "
        f"({latest_macro.decision_date.isoformat()})."
        if latest_macro and latest_macro.policy_rate is not None
        else "TCMB politika faizi verisi bulunmuyor."
    )
    signal_text = (
        f"Güncel bileşik skor sıralamasında ilk hisseler: {', '.join(top_tickers)}."
        if top_tickers
        else "Son 24 saatte hesaplanmış bileşik sinyal bulunmuyor."
    )
    summary = f"{signal_text} {rate_text} Bu özet kayıtlı verilerden otomatik derlenir."
    headline = f"BIST {session_name.capitalize()} Veri Özeti"
    # Do not turn row count into a bullish market call. Only sufficiently
    # confident scores contribute, and missing coverage remains neutral.
    scores = [
        float(row.composite_score)
        for row in top_signals
        if row.confidence is not None and row.confidence >= 0.5
    ]
    average_score = sum(scores) / len(scores) if scores else 50

    briefing = {
        "date": date_str,
        "session": session_name,
        "headline": headline,
        "market_mood": "BULLISH"
        if average_score >= 60
        else "BEARISH"
        if average_score < 40
        else "NEUTRAL",
        "summary": summary,
        "catalysts": catalysts,
        "sector_commentary": [],
        "actionable_takeaways": [
            "Bileşik skorları veri kapsamı ve güven düzeyiyle birlikte değerlendirin.",
            "KAP değerlendirmelerini kaynak bildirim ve yayın tarihiyle doğrulayın.",
        ],
        "generated_at": now.isoformat(),
    }

    # Redis'e 1 saat onbellekle
    try:
        await redis.setex(cache_key, 3600, json.dumps(briefing, ensure_ascii=False))
    except RedisError as exc:
        logger.warning("Briefing cache write failed: %s", exc)
    return briefing
