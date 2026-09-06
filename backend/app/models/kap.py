"""KAP bildirimleri ve ek dosyalari.

`KapDisclosure.disclosure_index`, KAP'in herkese acik bildirim numarasidir ve
dogal anahtar olarak kullanilir. Bir bildirim birden cok kodla iliskili
olabildigi icin kodlar JSON listesi olarak saklanir; isme dayali esleme
yapilmaz.

KAP ek indirme endpoint'i dosyayi ham olarak degil Java-serialized `byte[]`
icinde dondurur. Collector sarmalayiciyi cozer ve yalnizca asil dosya
baytlarini `KapAttachment.content` alanina yazar. Alan `deferred` oldugu icin
liste/detay sorgularinda buyuk dosyalar gereksiz yere RAM'e alinmaz.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

TICKER_CODES_TYPE = JSON().with_variant(JSONB, "postgresql")


class KapDisclosure(Base):
    __tablename__ = "kap_disclosure"
    __table_args__ = (
        Index("ix_kap_disclosure_ticker_codes_gin", "ticker_codes", postgresql_using="gin"),
    )

    disclosure_index: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    kap_title: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosure_class: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    disclosure_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    disclosure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ticker_codes: Mapped[list[str]] = mapped_column(TICKER_CODES_TYPE, default=list)

    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    has_multi_language_support: Mapped[bool] = mapped_column(Boolean, default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)

    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_list_item: Mapped[dict] = mapped_column(JSON)
    raw_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    attachments: Mapped[list["KapAttachment"]] = relationship(
        back_populates="disclosure",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KapDisclosure {self.disclosure_index}>"


class KapAttachment(Base):
    __tablename__ = "kap_attachment"

    obj_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    disclosure_index: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kap_disclosure.disclosure_index", ondelete="CASCADE"),
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(1024))
    file_extension: Mapped[str | None] = mapped_column(String(32), nullable=True)

    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    download_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    disclosure: Mapped[KapDisclosure] = relationship(back_populates="attachments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KapAttachment {self.obj_id} {self.file_name!r}>"
