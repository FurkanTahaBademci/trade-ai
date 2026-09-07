"""Gunluk fiyat (EOD) modeli.

Veri kaynagi: `isyatirimhisse.fetch_stock_data`. Bu kutuphane BIST icin
klasik OHLC degil, kendi alan adlandirmasini kullaniyor ve **acilis (open)
fiyati saglamiyor** (gunluk request'te sadece kapanis/min/max/AOF/hacim
dönüyor) — bu yuzden `price_daily` semasi plandaki "o/h/l/c" yerine
gercekte mevcut olan alanlari tutar. Acilis fiyati gerekirse Faz 1
sonrasinda ayri (muhtemelen ucretli/intraday) bir kaynak degerlendirilir.

Kutuphanenin dondurdugu ham kolonlar (bkz. .claude/PROGRESS.md Faz 1 notu):
    HGDG_HS_KODU   -> ticker
    HGDG_TARIH     -> date
    HGDG_KAPANIS   -> close
    HGDG_MIN/MAX   -> low/high
    HGDG_HACIM     -> volume (TL islem hacmi, adet degil)
    HGDG_AOF       -> avg_price (agirlikli ortalama fiyat)
    PD             -> market_cap_try
    DOLAR_BAZLI_FIYAT -> close_usd
"""

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date as SADate
from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_price_daily_ticker_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("instrument.ticker"), index=True)
    date: Mapped[date_type] = mapped_column(SADate, index=True)

    close: Mapped[float] = mapped_column(Numeric(18, 4))
    high: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    avg_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume_try: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    close_usd: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    market_cap_try: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PriceDaily {self.ticker} {self.date}>"
