"""Collector tarama araliklarini goruntuleme ve yonetme API'si."""

from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.scheduling.service import enqueue_schedule_now, list_schedules, update_schedule
from app.schemas.schedule import ScheduleOut, ScheduleRunOut, ScheduleUpdate

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def require_admin_token(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> str:
    settings = get_settings()
    if not settings.admin_api_token:
        if settings.environment.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ADMIN_API_TOKEN production ortaminda zorunludur",
            )
        return "local-development"
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz yonetim anahtari",
        )
    return "admin-token"


@router.get("", response_model=list[ScheduleOut])
async def get_schedules(db: Annotated[AsyncSession, Depends(get_db)]) -> list[ScheduleOut]:
    return await list_schedules(db)


@router.patch("/{name}", response_model=ScheduleOut)
async def patch_schedule(
    name: str,
    payload: ScheduleUpdate,
    request: Request,
    _admin: Annotated[str, Depends(require_admin_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduleOut:
    actor = request.client.host if request.client else "unknown"
    try:
        row = await update_schedule(
            db,
            name=name,
            interval_minutes=payload.interval_minutes,
            enabled=payload.enabled,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Takvim bulunamadi")
    return row


@router.post("/{name}/run", response_model=ScheduleRunOut)
async def run_schedule_now(
    name: str,
    request: Request,
    _admin: Annotated[str, Depends(require_admin_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduleRunOut:
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        row, enqueued, job_id, enqueued_at = await enqueue_schedule_now(
            db,
            redis,
            name=name,
            actor=request.client.host if request.client else "unknown",
        )
    finally:
        await redis.aclose()
    if row is None:
        raise HTTPException(status_code=404, detail="Takvim bulunamadi")
    return ScheduleRunOut(
        name=row.name,
        enqueued=enqueued,
        job_id=job_id,
        enqueued_at=enqueued_at,
    )
