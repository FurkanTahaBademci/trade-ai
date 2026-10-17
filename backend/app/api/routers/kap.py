"""KAP bildirimlerini listeleme, detay ve ek dosya endpoint'leri."""

from datetime import datetime
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.kap import KAP_FILE_URL, unwrap_java_serialized_byte_array
from app.collectors.kap_content import (
    clean_kap_body_text,
    is_kap_test_disclosure,
    not_kap_test_disclosure,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.models import KapAttachment, KapDisclosure
from app.schemas.kap import KapDisclosureDetailOut, KapDisclosureListOut

settings = get_settings()
router = APIRouter(prefix="/api/disclosures", tags=["disclosures"])


@router.get("", response_model=list[KapDisclosureListOut])
async def list_disclosures(
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    disclosure_class: Annotated[str | None, Query(max_length=32)] = None,
    before: Annotated[
        datetime | None, Query(description="Cursor: bu tarihten eski bildirimler")
    ] = None,
    before_index: Annotated[
        int | None,
        Query(ge=1, description="Ayni yayin zamanindaki bildirimler icin cursor index"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[KapDisclosure]:
    # KAP'in sistem test bildirimleri (KTEST vb.) eski kayitlarda DB'de kalmis
    # olabilir; ana sayfa dahil hicbir listede gosterilmez.
    stmt = (
        select(KapDisclosure)
        .where(not_kap_test_disclosure())
        .order_by(KapDisclosure.published_at.desc(), KapDisclosure.disclosure_index.desc())
    )
    if ticker:
        # Uretim DB'si PostgreSQL. JSONB cast'i `ticker_codes @> ['THYAO']`
        # semantigini acik hale getirir; alt-string eslesmesi yapmaz.
        stmt = stmt.where(cast(KapDisclosure.ticker_codes, JSONB).contains([ticker.upper()]))
    if disclosure_class:
        stmt = stmt.where(KapDisclosure.disclosure_class == disclosure_class.upper())
    if before and before_index:
        stmt = stmt.where(
            or_(
                KapDisclosure.published_at < before,
                and_(
                    KapDisclosure.published_at == before,
                    KapDisclosure.disclosure_index < before_index,
                ),
            )
        )
    elif before:
        stmt = stmt.where(KapDisclosure.published_at < before)
    result = await db.execute(stmt.limit(limit))
    return list(result.scalars().unique().all())


@router.get("/{disclosure_index}", response_model=KapDisclosureDetailOut)
async def get_disclosure(
    disclosure_index: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KapDisclosureDetailOut:
    disclosure = await db.get(KapDisclosure, disclosure_index)
    if disclosure is None or is_kap_test_disclosure(
        ticker_codes=disclosure.ticker_codes,
        kap_title=disclosure.kap_title,
        subject=disclosure.subject,
        summary=disclosure.summary,
        body_text=disclosure.body_text,
    ):
        raise HTTPException(status_code=404, detail="KAP bildirimi bulunamadi")
    # Temizlik okuma aninda da uygulanir: eski kayitlardaki sablon artiklari
    # (`oda_*|`, `[]`) migration gerekmeden kaybolur. ORM nesnesi degismez.
    out = KapDisclosureDetailOut.model_validate(disclosure)
    return out.model_copy(update={"body_text": clean_kap_body_text(out.body_text)})


@router.get("/{disclosure_index}/attachments/{obj_id}")
async def download_attachment(
    disclosure_index: int,
    obj_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    metadata = await db.execute(
        select(KapAttachment.file_name, KapAttachment.file_extension).where(
            KapAttachment.obj_id == obj_id,
            KapAttachment.disclosure_index == disclosure_index,
        )
    )
    row = metadata.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="KAP eki bulunamadi")

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.collector_user_agent}, timeout=30.0
        ) as client:
            resp = await client.get(
                KAP_FILE_URL.format(obj_id=obj_id),
                headers={"Referer": f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"},
            )
            if resp.status_code != 200 or not resp.content:
                raise HTTPException(status_code=502, detail="KAP sunucusundan ek dosya alinamadi")
            content = unwrap_java_serialized_byte_array(resp.content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"KAP eki indirilemedi: {exc}"
        ) from exc

    media_type = "application/pdf" if row.file_extension == "pdf" else "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.file_name)}"},
    )
