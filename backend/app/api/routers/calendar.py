"""Piyasa takvimi: TCMB PPK toplantilari + KAP bildirimlerinden turetilen olaylar."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.market_calendar.classifier import (
    EVENT_LABELS,
    KAP_PREFILTER_STEMS,
    EventType,
    classify_disclosure,
)
from app.models import KapDisclosure, MonetaryPolicyDecision
from app.schemas.calendar import CalendarEventOut

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

MAX_RANGE_DAYS = 400
KAP_ROW_LIMIT = 3000


@router.get("", response_model=list[CalendarEventOut])
async def list_calendar_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    types: Annotated[list[EventType] | None, Query()] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
) -> list[CalendarEventOut]:
    today = datetime.now(UTC).date()
    start = start or today.replace(day=1)
    end = end or (start + timedelta(days=60))
    if end < start:
        raise HTTPException(status_code=422, detail="Bitis tarihi baslangictan once olamaz")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Tarih araligi en fazla 400 gun olabilir")
    wanted = set(types) if types else set(EventType)
    ticker_filter = ticker.upper() if ticker else None
    events: list[CalendarEventOut] = []

    # Ticker filtresi PPK icin anlamsiz: hisse secilince makro olaylar gizlenir.
    if EventType.PPK in wanted and ticker_filter is None:
        stmt = (
            select(MonetaryPolicyDecision)
            .where(MonetaryPolicyDecision.decision_date >= start)
            .where(MonetaryPolicyDecision.decision_date <= end)
            .order_by(MonetaryPolicyDecision.decision_date)
        )
        for decision in (await db.scalars(stmt)).all():
            events.append(
                CalendarEventOut(
                    id=f"ppk-{decision.decision_no}",
                    date=decision.decision_date,
                    type=EventType.PPK,
                    type_label=EVENT_LABELS[EventType.PPK],
                    title=decision.title,
                    detail=(
                        None
                        if decision.policy_rate is None
                        else f"Politika faizi %{decision.policy_rate}"
                    ),
                    source="TCMB",
                    upcoming=decision.status == "SCHEDULED" and decision.decision_date >= today,
                )
            )

    if wanted - {EventType.PPK}:
        # Govde metni ve ekler gerekmez; yalniz siniflandirma kolonlari cekilir.
        stmt = (
            select(
                KapDisclosure.disclosure_index,
                KapDisclosure.published_at,
                KapDisclosure.kap_title,
                KapDisclosure.subject,
                KapDisclosure.disclosure_class,
                KapDisclosure.ticker_codes,
                KapDisclosure.event_date,
                KapDisclosure.event_detail,
            )
            # Olay tarihi biliniyorsa (genel kurul, hak kullanim) olay o gune yerlesir;
            # yayin tarihi pencere disinda kalsa bile gosterilir.
            .where(
                or_(
                    and_(
                        KapDisclosure.event_date.is_not(None),
                        KapDisclosure.event_date >= start,
                        KapDisclosure.event_date <= end,
                    ),
                    and_(
                        KapDisclosure.event_date.is_(None),
                        KapDisclosure.published_at >= start,
                        KapDisclosure.published_at < end + timedelta(days=1),
                    ),
                )
            )
        )
        patterns = [f"%{stem}%" for stem in KAP_PREFILTER_STEMS]
        text_filters = [KapDisclosure.kap_title.ilike(p) for p in patterns]
        text_filters += [KapDisclosure.subject.ilike(p) for p in patterns]
        text_filters.append(KapDisclosure.disclosure_class == "FR")
        stmt = stmt.where(or_(*text_filters))
        if ticker_filter:
            stmt = stmt.where(cast(KapDisclosure.ticker_codes, JSONB).contains([ticker_filter]))
        stmt = stmt.order_by(KapDisclosure.published_at, KapDisclosure.disclosure_index).limit(
            KAP_ROW_LIMIT
        )
        for row in (await db.execute(stmt)).all():
            result = classify_disclosure(
                title=row.kap_title, subject=row.subject, disclosure_class=row.disclosure_class
            )
            if result is None or result.event_type not in wanted:
                continue
            event_day = row.event_date or row.published_at.date()
            events.append(
                CalendarEventOut(
                    id=f"kap-{row.disclosure_index}",
                    date=event_day,
                    type=result.event_type,
                    type_label=EVENT_LABELS[result.event_type],
                    title=row.subject or row.kap_title,
                    detail=row.event_detail or result.detail,
                    source="KAP",
                    tickers=list(row.ticker_codes or []),
                    disclosure_index=row.disclosure_index,
                    upcoming=row.event_date is not None and event_day >= today,
                )
            )

    events.sort(key=lambda e: (e.date, e.id))
    return events
