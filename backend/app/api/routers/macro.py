"""TCMB faiz kararlari ve etki senaryolari endpoint'leri."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import MonetaryPolicyDecision
from app.schemas.macro import MonetaryPolicyDecisionOut

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/policy-decisions", response_model=list[MonetaryPolicyDecisionOut])
async def list_policy_decisions(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[Literal["PUBLISHED", "SCHEDULED"] | None, Query()] = None,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[MonetaryPolicyDecision]:
    stmt = select(MonetaryPolicyDecision)
    if status:
        stmt = stmt.where(MonetaryPolicyDecision.status == status)
    if start:
        stmt = stmt.where(MonetaryPolicyDecision.decision_date >= start)
    if end:
        stmt = stmt.where(MonetaryPolicyDecision.decision_date <= end)
    stmt = stmt.order_by(MonetaryPolicyDecision.decision_date.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())
