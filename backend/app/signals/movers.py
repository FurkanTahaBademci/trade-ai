"""Bilesik skoru en cok degisen hisseler (API ve gunluk ozet ortak kullanir)."""

from datetime import timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import CompositeSignalSnapshot
from app.schemas.signal import SignalMoverOut, SignalMoversOut
from app.signals.service import MODEL_VERSION


async def load_signal_movers(db: AsyncSession, *, days: int, limit: int) -> SignalMoversOut:
    """Son skor gunu ile `days` takvim gunu (veya daha) onceki en yakin skor gunu karsilastirilir."""
    latest = await db.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == MODEL_VERSION
        )
    )
    base = (
        await db.scalar(
            select(func.max(CompositeSignalSnapshot.as_of_date)).where(
                CompositeSignalSnapshot.model_version == MODEL_VERSION,
                CompositeSignalSnapshot.as_of_date <= latest - timedelta(days=days),
            )
        )
        if latest
        else None
    )
    if latest is None or base is None:
        return SignalMoversOut(as_of_date=latest, base_date=base, risers=[], fallers=[])

    current = aliased(CompositeSignalSnapshot)
    previous = aliased(CompositeSignalSnapshot)
    change = (current.composite_score - previous.composite_score).label("change")
    stmt = (
        select(
            current.ticker,
            current.composite_score,
            previous.composite_score.label("previous_score"),
            change,
            current.signal_label,
            previous.signal_label.label("previous_label"),
        )
        .join(
            previous,
            and_(
                previous.ticker == current.ticker,
                previous.model_version == current.model_version,
                previous.as_of_date == base,
            ),
        )
        .where(current.as_of_date == latest, current.model_version == MODEL_VERSION)
    )

    def to_out(rows) -> list[SignalMoverOut]:
        return [
            SignalMoverOut(
                ticker=row.ticker,
                composite_score=float(row.composite_score),
                previous_score=float(row.previous_score),
                change=float(row.change),
                signal_label=row.signal_label,
                previous_label=row.previous_label,
            )
            for row in rows
            if row.change != 0
        ]

    risers = (await db.execute(stmt.order_by(change.desc(), current.ticker).limit(limit))).all()
    fallers = (await db.execute(stmt.order_by(change.asc(), current.ticker).limit(limit))).all()
    return SignalMoversOut(
        as_of_date=latest,
        base_date=base,
        risers=[item for item in to_out(risers) if item.change > 0],
        fallers=[item for item in to_out(fallers) if item.change < 0],
    )
