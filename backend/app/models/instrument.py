"""Hisse evreni (instrument) modeli.

Veri kaynagi: KAP `GET /tr/api/company/items/IGS/A` (bkz.
collectors/instruments.py). Bu endpoint'in dogrulanmis alanlari icin
.claude/PROGRESS.md -> Faz 1 notlarina bak.

BILINEN VERI KALITESI SORUNU: KAP'in kendi veritabaninda Turkce karakterler
(ç, ğ, ı, ö, ş, ü) bir kismi bildirim/sirket icin kalici olarak bozulmus
(U+FFFD - "replacement character" - sunucu tarafinda, istemci decode hatasi
degil). `name`/`city` alanlarini sadece GORUNTULEME icin kullan; hicbir
esleme/karsilastirma mantigini isme dayandirma — `ticker` her zaman temiz
(ASCII) ve guvenilir.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Instrument(Base):
    __tablename__ = "instrument"

    # BIST hisse kodu (orn. "THYAO"). Her zaman temiz ASCII - tum sistemde
    # hisseleri birbirine baglayan tek dogal anahtar budur.
    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)

    name: Mapped[str] = mapped_column(String(255))
    """KAP'tan gelen sirket unvani. Turkce karakter bozulmasi olabilir (yukari bak)."""

    city: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Bir KAP uyesinin birden cok pay sinifi/ticker'i olabilir (orn. KRDMA/B/D).
    kap_member_oid: Mapped[str] = mapped_column(String(64), index=True)
    mkk_member_oid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    """KAP `kapMemberState == 'A'` karsiligi. Pasif sirketler icin fiyat/KAP
    toplama collector'lari atlanabilir (Faz 2+)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Instrument {self.ticker}>"
