"""Yoneticinin sunucuda tutulan izleme listesi (bildirimler bundan beslenir)."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
