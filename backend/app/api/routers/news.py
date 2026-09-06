"""RSS haberlerini listeleme ve detay endpoint'leri."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import NewsArticle
from app.schemas.news import NewsArticleDetailOut, NewsArticleListOut

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsArticleListOut])
async def list_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    before: Annotated[
        datetime | None, Query(description="Cursor: bu tarihten eski haberler")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[NewsArticle]:
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
    if source:
        stmt = stmt.where(NewsArticle.source == source.lower())
    if ticker:
        stmt = stmt.where(cast(NewsArticle.ticker_codes, JSONB).contains([ticker.upper()]))
    if before:
        stmt = stmt.where(NewsArticle.published_at < before)
    result = await db.execute(stmt.limit(limit))
    return list(result.scalars().all())


@router.get("/{article_id}", response_model=NewsArticleDetailOut)
async def get_news_article(
    article_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NewsArticle:
    article = await db.get(NewsArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Haber bulunamadi")
    return article
