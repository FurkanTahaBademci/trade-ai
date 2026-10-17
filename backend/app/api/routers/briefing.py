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
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.db import get_db
from app.core.redis import get_redis
from app.models.kap import KapDisclosure
from app.models.llm_evaluation import LlmEvaluation
from app.models.macro import MonetaryPolicyDecision
from app.models.news import NewsArticle
from app.models.signal import CompositeSignalSnapshot
from app.signals.service import MODEL_VERSION

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = logging.getLogger(__name__)


# Bultende ve ana sayfa odak kartinda gosterilecek en dusuk LLM etki puani.
# Altindaki gelismeler (ornegin "okullar tatil mi" haberi, etki 0) mansete cikmaz.
MIN_CATALYST_IMPACT = 30
# Katalizor sirasi: etki puani, yayindan bu yana gecen her saat icin bu kadar
# puan duser (24 saatlik pencerede en fazla ~24 puan).
RECENCY_PENALTY_PER_HOUR = 1.0
# Duygu skoru bu esigin altindaysa olay yonu "notr" kabul edilir.
SENTIMENT_DEADBAND = 0.15
MAX_CATALYSTS = 6

# LLM sema degerleri (app.schemas.llm.EventType) -> arayuz metni. Web'deki
# eventName() eslemesiyle ayni sozluk.
EVENT_TYPE_LABELS = {
    "earnings": "Finansal sonuç",
    "corporate_action": "Kurumsal aksiyon",
    "contract": "Sözleşme",
    "financing": "Finansman",
    "governance": "Yönetim",
    "regulatory": "Düzenleme",
    "macro": "Makro",
    "market": "Piyasa",
    "legal": "Hukuk",
    "operations": "Operasyon",
    "other": "Diğer",
}


def event_label(event_type: str | None) -> str:
    if not event_type:
        return "Genel"
    return EVENT_TYPE_LABELS.get(event_type, event_type)


def sentiment_direction(sentiment) -> str:
    value = float(sentiment or 0)
    if value >= SENTIMENT_DEADBAND:
        return "POSITIVE"
    if value <= -SENTIMENT_DEADBAND:
        return "NEGATIVE"
    return "NEUTRAL"


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def rank_score(impact: float, published_at: datetime | None, now: datetime) -> float:
    """Etki puanini guncellikle dengeler: eski ama yuksek etkili gelisme,
    taze ama orta etkili gelismenin onune ancak belirgin farkla gecer."""
    published = _aware(published_at)
    age_hours = max(0.0, (now - published).total_seconds() / 3600) if published else 24.0
    return float(impact) - RECENCY_PENALTY_PER_HOUR * age_hours


def _latest_evaluation_ids(source_type: str, since: datetime):
    """Her kaynak icin tek degerlendirme: en yuksek tier, sonra en yeni.

    Tier 2 sonucu Tier 1'i duzeltir; ayni haberin iki kaydi bultende iki kez
    gorunmez ve Tier 1'in abartili puani Tier 2'nin onune gecmez.
    """
    return (
        select(LlmEvaluation.id)
        .where(
            LlmEvaluation.source_type == source_type,
            LlmEvaluation.status == "succeeded",
            LlmEvaluation.completed_at >= since,
        )
        .ext(distinct_on(LlmEvaluation.source_id))
        .order_by(
            LlmEvaluation.source_id,
            desc(LlmEvaluation.tier),
            desc(LlmEvaluation.completed_at),
        )
    )


# Bultende kullanilan kolonlar; input_document/raw_response gibi buyuk alanlar cekilmez.
_CATALYST_COLUMNS = load_only(
    LlmEvaluation.id,
    LlmEvaluation.source_id,
    LlmEvaluation.impact_score,
    LlmEvaluation.sentiment_score,
    LlmEvaluation.event_type,
    LlmEvaluation.ticker_codes,
    LlmEvaluation.summary,
)


async def load_catalysts(
    db: AsyncSession, *, since: datetime, now: datetime, limit: int = MAX_CATALYSTS
) -> list[dict[str, Any]]:
    """Son 24 saatin LLM etki puani esigini gecen haber/KAP gelismeleri,
    etki + guncellik sirasiyla."""
    kap_stmt = (
        select(
            LlmEvaluation,
            KapDisclosure.subject,
            KapDisclosure.kap_title,
            KapDisclosure.published_at,
        )
        .options(_CATALYST_COLUMNS)
        .join(KapDisclosure, KapDisclosure.disclosure_index == LlmEvaluation.source_id)
        .where(
            LlmEvaluation.id.in_(_latest_evaluation_ids("kap", since)),
            LlmEvaluation.impact_score >= MIN_CATALYST_IMPACT,
            KapDisclosure.published_at >= since,
            KapDisclosure.published_at <= now,
        )
        .order_by(desc(LlmEvaluation.impact_score), desc(KapDisclosure.published_at))
        .limit(limit * 3)
    )
    news_stmt = (
        select(
            LlmEvaluation,
            NewsArticle.title,
            NewsArticle.summary,
            NewsArticle.published_at,
        )
        .options(_CATALYST_COLUMNS)
        .join(NewsArticle, NewsArticle.id == LlmEvaluation.source_id)
        .where(
            LlmEvaluation.id.in_(_latest_evaluation_ids("news", since)),
            LlmEvaluation.impact_score >= MIN_CATALYST_IMPACT,
            NewsArticle.published_at >= since,
            NewsArticle.published_at <= now,
        )
        .order_by(desc(LlmEvaluation.impact_score), desc(NewsArticle.published_at))
        .limit(limit * 3)
    )

    candidates: list[dict[str, Any]] = []
    for ev, subject, kap_title, published_at in (await db.execute(kap_stmt)).all():
        candidates.append(
            _catalyst(
                ev,
                category="KAP",
                title=subject or kap_title or event_label(ev.event_type),
                description=ev.summary or "",
                href=f"/kap/{ev.source_id}",
                published_at=published_at,
                now=now,
            )
        )
    for ev, title, article_summary, published_at in (await db.execute(news_stmt)).all():
        fallback = (article_summary or "").strip()
        if len(fallback) > 240:
            fallback = fallback[:237].rstrip() + "…"
        candidates.append(
            _catalyst(
                ev,
                category="HABER",
                title=title,
                description=ev.summary or fallback,
                href=f"/haberler/{ev.source_id}",
                published_at=published_at,
                now=now,
            )
        )
    candidates.sort(key=lambda item: item["_rank"], reverse=True)
    for item in candidates:
        item.pop("_rank")
    return candidates[:limit]


def _catalyst(
    ev: LlmEvaluation,
    *,
    category: str,
    title: str,
    description: str,
    href: str,
    published_at: datetime | None,
    now: datetime,
) -> dict[str, Any]:
    published = _aware(published_at)
    return {
        "title": title,
        "category": category,
        "event_type": ev.event_type,
        "event_label": event_label(ev.event_type),
        "impact": sentiment_direction(ev.sentiment_score),
        "impact_score": int(ev.impact_score),
        "tickers": ev.ticker_codes or [],
        "description": description,
        "href": href,
        "evaluation_id": ev.id,
        "published_at": published.isoformat() if published else None,
        "_rank": rank_score(ev.impact_score, published, now),
    }


@router.get("/focus")
async def get_market_focus(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Ana sayfa "AI gundem ozeti": son 24 saatin en yuksek etkili gelismesi.

    Esigi gecen gelisme yoksa `item` null doner; arayuz sakin gun durumunu gosterir.
    """
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)
    candidates = await load_catalysts(db, since=since, now=now, limit=20)
    # Odak karti guncellik cezasi olmadan en yuksek etkiyi gosterir; esitlikte yenisi.
    candidates.sort(
        key=lambda item: (item["impact_score"], item["published_at"] or ""), reverse=True
    )
    return {
        "item": candidates[0] if candidates else None,
        "threshold": MIN_CATALYST_IMPACT,
        "window_hours": 24,
    }


def _turkish_rate(value) -> str:
    """37 -> "37", 37.5 -> "37,5" (gereksiz ondalik ve nokta ayirac yazilmaz)."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


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
    cache_key = f"ai:briefing:v3:{date_str}:{session_name}"

    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Briefing cache read failed: %s", exc)

    # 1. Son 24 saatin etki + guncellik sirali haber/KAP gelismeleri
    catalysts = await load_catalysts(db, since=since, now=now)

    # 2. TCMB son politika faizi
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
    # Yalniz uc kolon gerekir; ~600 satirin kanit/bilesen JSON'lari cekilmez.
    pos_signals_stmt = (
        select(CompositeSignalSnapshot)
        .options(
            load_only(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.confidence,
            )
        )
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

    rate_text = (
        f"Son kayıtlı TCMB politika faizi %{_turkish_rate(latest_macro.policy_rate)} "
        f"({latest_macro.decision_date:%d.%m.%Y})."
        if latest_macro and latest_macro.policy_rate is not None
        else "TCMB politika faizi verisi bulunmuyor."
    )
    signal_text = (
        f"Güncel bileşik skor sıralamasında ilk hisseler: {', '.join(top_tickers)}."
        if top_tickers
        else "Son 24 saatte hesaplanmış bileşik sinyal bulunmuyor."
    )
    if catalysts:
        lead = catalysts[0]
        lead_tickers = f" ({', '.join(lead['tickers'][:3])})" if lead["tickers"] else ""
        catalyst_text = f"Öne çıkan gelişme: {lead['title']}{lead_tickers}."
    else:
        catalyst_text = (
            f"Son 24 saatte etki puanı {MIN_CATALYST_IMPACT} ve üzeri haber/KAP gelişmesi yok."
        )
    summary = (
        f"{catalyst_text} {signal_text} {rate_text} Bu özet kayıtlı verilerden otomatik derlenir."
    )
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
        # Ruh hali hesabina giren guvenilir skor sayisi; 0 ise arayuz
        # "Yetersiz veri" gosterir, "Notr" demez.
        "mood_sample_size": len(scores),
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
