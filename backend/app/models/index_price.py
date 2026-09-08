"""Gunluk BIST endeks (BIST100/XU100) degeri modeli.

Veri kaynagi: `isyatirimhisse.fetch_index_data` — is Yatirim'in ayri endeks
uc noktasi, hisse fiyatlarindan (`price_daily`) farkli sema doner: sadece
kapanis degeri, hacim/PD/AOF yok. Bu yuzden `price_daily`'ye eklenmek yerine
kendi tablosunda tutulur — bir endeks `instrument` tablosundaki bir sirket
degildir, `price_daily.ticker` foreign key'ine uymaz.

Kullanim: paper portfoy ve backtest performans grafiklerinde gercek BIST100
karsilastirma (benchmark) cizgisi icin (bkz. app/api/routers/index_prices.py).
"""

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date as SADate
from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class IndexDaily(Base):
    __tablename__ = "index_daily"
    __table_args__ = (UniqueConstraint("index_code", "date", name="uq_index_daily_code_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    index_code: Mapped[str] = mapped_column(String(16), index=True)
    date: Mapped[date_type] = mapped_column(SADate, index=True)
    value: Mapped[float] = mapped_column(Numeric(18, 4))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IndexDaily {self.index_code} {self.date}>"
