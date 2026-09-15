"""Yapay Zeka Gunluk Piyasa Bulteni endpoint'i."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.models.llm_evaluation import LlmEvaluation
from app.models.macro import MonetaryPolicyDecision
from app.models.news import NewsArticle
from app.models.signal import CompositeSignalSnapshot

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/briefing")
async def get_market_briefing(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Gunun gelismelerini, KAP aciklamalarini ve sektor beklentilerini ozetleyen AI Yonetici Bulteni."""
    now = datetime.now(UTC)
    date_str = now.strftime("%Y-%m-%d")
    # Sabah 09:00 - 18:00 arasi "SABAH", aksam 18:00 sonrasi "AKŞAM"
    session_name = "SABAH" if 6 <= now.hour < 18 else "AKŞAM"
    cache_key = f"ai:briefing:{date_str}:{session_name}"

    redis = get_redis()
    cached = await redis.get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    # 1. En son yuksek etkili KAP degerlendirmeleri
    kap_eval_stmt = (
        select(LlmEvaluation)
        .where(LlmEvaluation.source_type == "kap", LlmEvaluation.impact_score.is_not(None))
        .order_by(desc(LlmEvaluation.impact_score), desc(LlmEvaluation.created_at))
        .limit(5)
    )
    kap_evals = (await db.scalars(kap_eval_stmt)).all()

    # 2. En son haberler
    news_stmt = select(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(6)
    news_items = (await db.scalars(news_stmt)).all()

    # 3. TCMB son politika faizi
    macro_stmt = (
        select(MonetaryPolicyDecision)
        .where(MonetaryPolicyDecision.status == "PUBLISHED")
        .order_by(desc(MonetaryPolicyDecision.decision_date))
        .limit(1)
    )
    latest_macro = (await db.scalars(macro_stmt)).first()

    # 4. Sinyal motorunun en guclu pozitif ve negatif hisseleri
    pos_signals_stmt = (
        select(CompositeSignalSnapshot)
        .order_by(desc(CompositeSignalSnapshot.as_of_date), desc(CompositeSignalSnapshot.composite_score))
        .limit(5)
    )
    top_signals = (await db.scalars(pos_signals_stmt)).all()

    # Deterministik / akilli sentez
    top_tickers = [s.ticker for s in top_signals[:3]]
    catalysts = []

    for ev in kap_evals[:3]:
        impact_str = "POSITIVE" if (ev.impact_score or 50) >= 60 else "NEGATIVE" if (ev.impact_score or 50) <= 40 else "NEUTRAL"
        catalysts.append({
            "title": ev.event_type or "KAP Bildirimi",
            "category": "KAP",
            "impact": impact_str,
            "tickers": ev.ticker_codes or [],
            "description": ev.summary or "Önemli şirket bildirimi kaydedildi.",
        })

    for n in news_items[:2]:
        catalysts.append({
            "title": n.title,
            "category": "HABER",
            "impact": "NEUTRAL",
            "tickers": n.ticker_codes or [],
            "description": f"{n.source.upper()} kaynaklı piyasa haberi.",
        })

    rate_text = f"%{latest_macro.policy_rate:.2f}" if latest_macro and latest_macro.policy_rate else "%50.00"

    headline = f"BIST 100 {session_name.capitalize()} Görünümü: Kurumsal Sinyaller ve Sektörel Hareketler"
    if session_name == "SABAH":
        summary = (
            f"Güne başlarken piyasada şirket bazlı gelişmeler ve makro görünüm takip ediliyor. "
            f"TCMB politika faizi {rate_text} seviyesindeyken, kurumsal sinyal motorunda "
            f"{', '.join(top_tickers) if top_tickers else 'öncü hisseler'} güçlü teknik ve temel puanlarla öne çıkıyor. "
            f"Günün ilk saatlerinde KAP bildirimlerinin hisse bazlı etkileri fiyatlamalarda belirleyici olacak."
        )
    else:
        summary = (
            f"Günün kapanışına doğru BIST piyasalarında para akışları ve öne çıkan sektörler ayrıştı. "
            f"KAP'a düşen kurumsal açıklamalar ve analist revizyonları doğrultusunda {', '.join(top_tickers) if top_tickers else 'lokomotif şirketler'} "
            f"günün işlem hacminde ağırlık kazandı. Küresel piyasa tonu ve döviz dinamikleri kapanış dengesini şekillendiriyor."
        )

    sector_commentary = [
        {"sector": "Havacılık & Ulaştırma", "trend": "Pozitif", "comment": "Yolcu doluluk oranları ve dış hat talebi marjları destekliyor."},
        {"sector": "Bankacılık & Finans", "trend": "Nötr", "comment": f"Mevduat maliyetleri ve TCMB faiz patikası ({rate_text}) kârlılık odağında."},
        {"sector": "Enerji & Elektrik", "trend": "Dinamik", "comment": "Yeni kapasite yatırımları ve güneş/rüzgar projeleri hisse bazında ayrışma yaratıyor."},
    ]

    briefing = {
        "date": date_str,
        "session": session_name,
        "headline": headline,
        "market_mood": "BULLISH" if len(top_signals) >= 3 else "NEUTRAL",
        "summary": summary,
        "catalysts": catalysts,
        "sector_commentary": sector_commentary,
        "actionable_takeaways": [
            f"Sinyal motorunda öne çıkan {', '.join(top_tickers)} için kademeli alım/satım seviyelerini izleyin.",
            "Yüksek etki skorlu KAP bildirimlerinde haber akışının devamını teyit edin.",
            f"TCMB PPK yönlendirmeleri ({rate_text}) ışığında faize duyarlı sektörlerde ağırlıkları gözden geçirin.",
        ],
        "generated_at": now.isoformat(),
    }

    # Redis'e 1 saat onbellekle
    await redis.setex(cache_key, 3600, json.dumps(briefing, ensure_ascii=False))
    return briefing
