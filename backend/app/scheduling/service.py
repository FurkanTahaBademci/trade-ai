"""PostgreSQL kalicilikli ve Redis kuyruklu dinamik is takvimi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.schedule import CollectorSchedule, ScheduleAuditLog


@dataclass(frozen=True)
class ScheduleDefinition:
    name: str
    label: str
    job_name: str
    default_interval_minutes: int
    minimum_interval_minutes: int
    initial_hour: int | None = None
    initial_minute: int = 0


SCHEDULE_DEFINITIONS: tuple[ScheduleDefinition, ...] = (
    ScheduleDefinition("kap", "KAP bildirimleri", "collect_kap", 5, 5),
    ScheduleDefinition("news", "Haber akisi", "collect_news", 5, 5),
    ScheduleDefinition("evaluations", "AI degerlendirmeleri", "evaluate_sources", 10, 10),
    ScheduleDefinition("signals", "Bilesik sinyaller", "compute_signals", 10, 5),
    ScheduleDefinition("instruments", "Hisse evreni", "collect_instruments", 1440, 60, 6),
    ScheduleDefinition(
        "tcmb_policy", "TCMB faiz kararlari", "collect_tcmb_policy", 1440, 60, 6, 30
    ),
    ScheduleDefinition("fundamentals", "Temel analiz", "collect_fundamentals", 1440, 60, 7),
    ScheduleDefinition("analysts", "Analist gorusleri", "collect_analysts", 1440, 60, 7, 30),
    ScheduleDefinition(
        "institutional_reports", "Kurum raporlari", "collect_institutional_reports", 1440, 60, 7, 45
    ),
    ScheduleDefinition("prices", "EOD fiyatlari", "collect_prices", 1440, 60, 18, 30),
    ScheduleDefinition("paper_portfolio", "Paper portfoy", "run_paper_portfolio", 1440, 60, 18, 46),
    ScheduleDefinition("fund_flows", "TEFAS fon akimi", "collect_fund_flows", 1440, 60, 20),
)
DEFINITION_BY_NAME = {item.name: item for item in SCHEDULE_DEFINITIONS}


def next_initial_run(definition: ScheduleDefinition, now: datetime | None = None) -> datetime:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if definition.initial_hour is None:
        return current + timedelta(minutes=definition.default_interval_minutes)

    local_tz = ZoneInfo(get_settings().tz)
    local_now = current.astimezone(local_tz)
    candidate = local_now.replace(
        hour=definition.initial_hour,
        minute=definition.initial_minute,
        second=0,
        microsecond=0,
    )
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


def advance_run(previous: datetime, interval_minutes: int, now: datetime | None = None) -> datetime:
    """Geciken isi bir kez kuyrukladiktan sonra gelecekteki ilk slotu bulur."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    candidate = previous.astimezone(UTC)
    interval = timedelta(minutes=interval_minutes)
    if candidate > current:
        return candidate
    skipped = int((current - candidate) // interval) + 1
    return candidate + interval * skipped


async def ensure_default_schedules(
    db: AsyncSession, *, now: datetime | None = None
) -> list[CollectorSchedule]:
    rows = list((await db.execute(select(CollectorSchedule))).scalars().all())
    existing = {row.name: row for row in rows}
    for definition in SCHEDULE_DEFINITIONS:
        if definition.name in existing:
            continue
        row = CollectorSchedule(
            name=definition.name,
            label=definition.label,
            job_name=definition.job_name,
            interval_minutes=definition.default_interval_minutes,
            minimum_interval_minutes=definition.minimum_interval_minutes,
            enabled=True,
            next_run_at=next_initial_run(definition, now),
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


async def list_schedules(db: AsyncSession) -> list[CollectorSchedule]:
    await ensure_default_schedules(db)
    await db.commit()
    result = await db.execute(select(CollectorSchedule).order_by(CollectorSchedule.label))
    return list(result.scalars().all())


async def update_schedule(
    db: AsyncSession,
    *,
    name: str,
    interval_minutes: int | None,
    enabled: bool | None,
    actor: str,
    now: datetime | None = None,
) -> CollectorSchedule | None:
    await ensure_default_schedules(db, now=now)
    row = await db.get(CollectorSchedule, name)
    if row is None:
        return None
    if interval_minutes is not None and interval_minutes < row.minimum_interval_minutes:
        raise ValueError(f"Minimum aralik {row.minimum_interval_minutes} dakikadir")

    current = (now or datetime.now(UTC)).astimezone(UTC)
    old_value = {"interval_minutes": row.interval_minutes, "enabled": row.enabled}
    if interval_minutes is not None:
        row.interval_minutes = interval_minutes
    if enabled is not None:
        row.enabled = enabled
    row.next_run_at = current + timedelta(minutes=row.interval_minutes) if row.enabled else None
    new_value = {"interval_minutes": row.interval_minutes, "enabled": row.enabled}
    db.add(
        ScheduleAuditLog(
            schedule_name=row.name,
            action="updated",
            actor=actor,
            old_value=old_value,
            new_value=new_value,
        )
    )
    await db.commit()
    await db.refresh(row)
    return row


async def enqueue_schedule_now(
    db: AsyncSession,
    redis,
    *,
    name: str,
    actor: str,
    now: datetime | None = None,
) -> tuple[CollectorSchedule | None, bool, str, datetime]:
    await ensure_default_schedules(db, now=now)
    row = await db.get(CollectorSchedule, name)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if row is None:
        return None, False, "", current
    job_id = f"manual:{name}:{current.isoformat()}"
    job = await redis.enqueue_job(row.job_name, _job_id=job_id)
    row.last_enqueued_at = current
    db.add(
        ScheduleAuditLog(
            schedule_name=row.name,
            action="run_now",
            actor=actor,
            old_value={},
            new_value={"job_id": job_id, "enqueued": job is not None},
        )
    )
    await db.commit()
    return row, job is not None, job_id, current


async def dispatch_due_schedules(ctx: dict) -> dict:
    """Dakikalik tick: vadesi gelen isleri bir kez Redis kuyruguna ekler."""
    redis = ctx["redis"]
    acquired = await redis.set("schedule:dispatcher:lock", "1", ex=55, nx=True)
    if not acquired:
        return {"status": "locked", "enqueued": 0}

    from app.core.db import session_factory

    now = datetime.now(UTC)
    enqueued = 0
    async with session_factory() as db:
        await ensure_default_schedules(db, now=now)
        await db.commit()
        stmt = (
            select(CollectorSchedule)
            .where(
                CollectorSchedule.enabled.is_(True),
                CollectorSchedule.next_run_at.is_not(None),
                CollectorSchedule.next_run_at <= now,
            )
            .order_by(CollectorSchedule.next_run_at)
            .with_for_update(skip_locked=True)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for row in rows:
            slot = row.next_run_at or now
            job_id = f"schedule:{row.name}:{int(slot.timestamp())}"
            job = await redis.enqueue_job(row.job_name, _job_id=job_id)
            row.last_enqueued_at = now
            row.next_run_at = advance_run(slot, row.interval_minutes, now)
            enqueued += int(job is not None)
        await db.commit()
    return {"status": "ok", "due": len(rows), "enqueued": enqueued}
