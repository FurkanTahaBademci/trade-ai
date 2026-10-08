"""RSS haberlerini listeleme ve detay endpoint'leri."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import LlmEvaluation, NewsArticle
from app.schemas.news import NewsArticleDetailOut, NewsArticleListOut

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsArticleListOut])
async def list_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    mode: Annotated[
        Literal["smart", "chronological"],
        Query(description="Sıralama modu: 'smart' (önem + güncellik) veya 'chronological' (yalnızca tarih)"),
    ] = "smart",
    min_impact: Annotated[
        int | None,
        Query(ge=0, le=100, description="Minimum etki puanı filtresi"),
    ] = None,
    before: Annotated[
        datetime | None, Query(description="Cursor: bu tarihten eski haberler")
    ] = None,
    before_id: Annotated[
        int | None,
        Query(ge=1, description="Ayni yayin zamanindaki haberler icin cursor ID"),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Sayfalama ofseti")] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[NewsArticleListOut]:
    is_chronological = mode == "chronological" or before is not None

    # Succeeded evaluations ranked by tier and id to pick the best evaluation per article
    eval_rn = func.row_number().over(
        partition_by=LlmEvaluation.source_id,
        order_by=[LlmEvaluation.tier.desc(), LlmEvaluation.id.desc()],
    ).label("eval_rn")

    eval_subq = (
        select(
            LlmEvaluation.source_id.label("source_id"),
            LlmEvaluation.impact_score.label("impact_score"),
            LlmEvaluation.sentiment_score.label("sentiment_score"),
            LlmEvaluation.event_type.label("event_type"),
            eval_rn,
        )
        .where(
            LlmEvaluation.source_type == "news",
            LlmEvaluation.status == "succeeded",
        )
        .subquery("eval_subq")
    )

    latest_eval = (
        select(
            eval_subq.c.source_id,
            eval_subq.c.impact_score,
            eval_subq.c.sentiment_score,
            eval_subq.c.event_type,
        )
        .where(eval_subq.c.eval_rn == 1)
        .subquery("latest_eval")
    )

    stmt = select(
        NewsArticle,
        latest_eval.c.impact_score,
        latest_eval.c.sentiment_score,
        latest_eval.c.event_type,
    ).outerjoin(latest_eval, NewsArticle.id == latest_eval.c.source_id)

    if source:
        stmt = stmt.where(NewsArticle.source == source.lower())
    if ticker:
        stmt = stmt.where(cast(NewsArticle.ticker_codes, JSONB).contains([ticker.upper()]))

    if is_chronological:
        # Kronolojik mod: Tüm haberler normal yayin sirasinda
        if before and before_id:
            stmt = stmt.where(
                or_(
                    NewsArticle.published_at < before,
                    and_(NewsArticle.published_at == before, NewsArticle.id < before_id),
                )
            )
        elif before:
            stmt = stmt.where(NewsArticle.published_at < before)
        stmt = stmt.order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
    else:
        # Akilli (smart) mod: Önem derecesi ve güncellik ortak kombinasyonu.
        # Önemsiz (0 puanli) haberler filtrelenir.
        if min_impact is not None:
            stmt = stmt.where(latest_eval.c.impact_score >= min_impact)
        elif ticker:
            # Belirli hisse icin: 0 puanli spamler filtrelenir, henuz degerlendirilmemisler korunur
            stmt = stmt.where(or_(latest_eval.c.impact_score.is_(None), latest_eval.c.impact_score > 0))
        else:
            # Genel akis: Sadece pozitif etki puanina sahip onemli haberler
            stmt = stmt.where(latest_eval.c.impact_score > 0)

        # Zaman asimi / guncellik fonksiyonu: impact / ((saat + 2)^0.7)
        hours_elapsed = func.greatest(
            (func.extract("epoch", func.now() - NewsArticle.published_at) / 3600.0),
            0.0,
        )
        impact = func.coalesce(latest_eval.c.impact_score, 20)
        smart_score = impact / func.power(hours_elapsed + 2.0, 0.7)

        stmt = stmt.order_by(smart_score.desc(), NewsArticle.published_at.desc(), NewsArticle.id.desc())

    if offset > 0 and not before:
        stmt = stmt.offset(offset)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    articles: list[NewsArticleListOut] = []
    for row in rows:
        if isinstance(row, (tuple, list)) or hasattr(row, "__getitem__"):
            article = row[0]
            impact = row[1] if len(row) > 1 else None
            sentiment = row[2] if len(row) > 2 else None
            event = row[3] if len(row) > 3 else None
        else:
            article = row
            impact = getattr(article, "impact_score", None)
            sentiment = getattr(article, "sentiment_score", None)
            event = getattr(article, "event_type", None)

        articles.append(
            NewsArticleListOut(
                id=article.id,
                source=article.source,
                canonical_url=article.canonical_url,
                title=article.title,
                summary=article.summary,
                author=article.author,
                image_url=article.image_url,
                published_at=article.published_at,
                ticker_codes=article.ticker_codes,
                impact_score=impact,
                sentiment_score=float(sentiment) if sentiment is not None else None,
                event_type=event,
            )
        )
    return articles


@router.get("/{article_id}", response_model=NewsArticleDetailOut)
async def get_news_article(
    article_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NewsArticleDetailOut:
    article = await db.get(NewsArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Haber bulunamadi")

    # Fetch latest evaluation if available
    eval_stmt = (
        select(LlmEvaluation)
        .where(
            LlmEvaluation.source_type == "news",
            LlmEvaluation.source_id == article_id,
            LlmEvaluation.status == "succeeded",
        )
        .order_by(LlmEvaluation.tier.desc(), LlmEvaluation.id.desc())
        .limit(1)
    )
    eval_res = await db.execute(eval_stmt)
    evaluation = eval_res.scalars().first()

    return NewsArticleDetailOut(
        id=article.id,
        source=article.source,
        canonical_url=article.canonical_url,
        title=article.title,
        summary=article.summary,
        author=article.author,
        image_url=article.image_url,
        published_at=article.published_at,
        ticker_codes=article.ticker_codes,
        source_guid=article.source_guid,
        raw_entry=article.raw_entry,
        fetched_at=article.fetched_at,
        updated_at=article.updated_at,
        impact_score=evaluation.impact_score if evaluation else None,
        sentiment_score=float(evaluation.sentiment_score) if evaluation and evaluation.sentiment_score is not None else None,
        event_type=evaluation.event_type if evaluation else None,
    )
