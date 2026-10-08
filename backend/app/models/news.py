"""RSS kaynaklarindan toplanan haber metadatasi.

Kaynak URL'leri takip parametreleri veya fragment'ler yuzunden degisebildigi
icin idempotency anahtari normalize edilmis `canonical_url` degerinin SHA-256
ozetidir. URL'nin kendisi inceleme ve API ciktilari icin ayrica saklanir.

Ticker eslemesi yalnizca haber metninde/URL'sinde acikca gecen ve instrument
tablosunda var olan kodlardan uretilir. Sirket unvanindan tahmin yapilmaz.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

NEWS_TICKER_CODES_TYPE = JSON().with_variant(JSONB, "postgresql")


class NewsArticle(Base):
    __tablename__ = "news_article"
    __table_args__ = (
        Index("ix_news_article_source_published", "source", "published_at"),
        Index("ix_news_article_ticker_codes_gin", "ticker_codes", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    source_guid: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    canonical_url: Mapped[str] = mapped_column(String(2048))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)

    title: Mapped[str] = mapped_column(String(1024))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ticker_codes: Mapped[list[str]] = mapped_column(NEWS_TICKER_CODES_TYPE, default=list)

    raw_entry: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NewsArticle {self.source} {self.id} {self.title!r}>"
