"""Haber API cikti semalari."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NewsArticleListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    canonical_url: str
    title: str
    summary: str | None
    author: str | None
    image_url: str | None
    published_at: datetime
    ticker_codes: list[str]
    impact_score: int | None = None
    sentiment_score: float | None = None
    event_type: str | None = None


class NewsArticleDetailOut(NewsArticleListOut):
    source_guid: str | None
    raw_entry: dict
    fetched_at: datetime
    updated_at: datetime
