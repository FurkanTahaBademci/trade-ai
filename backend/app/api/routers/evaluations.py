"""LLM degerlendirmelerini listeleme ve denetim detayi endpoint'leri."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import LlmEvaluation
from app.schemas.llm import LlmEvaluationDetailOut, LlmEvaluationListOut

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("", response_model=list[LlmEvaluationListOut])
async def list_evaluations(
    db: Annotated[AsyncSession, Depends(get_db)],
    source_type: Annotated[Literal["news", "kap"] | None, Query()] = None,
    source_id: Annotated[int | None, Query(ge=1)] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    tier: Annotated[int | None, Query(ge=1, le=2)] = None,
    status: Annotated[Literal["running", "succeeded", "failed"] | None, Query()] = None,
    before: Annotated[
        datetime | None, Query(description="Cursor: bu tarihten eski degerlendirmeler")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[LlmEvaluation]:
    stmt = select(LlmEvaluation).order_by(
        LlmEvaluation.created_at.desc(), LlmEvaluation.id.desc()
    )
    if source_type:
        stmt = stmt.where(LlmEvaluation.source_type == source_type)
    if source_id:
        stmt = stmt.where(LlmEvaluation.source_id == source_id)
    if ticker:
        stmt = stmt.where(cast(LlmEvaluation.ticker_codes, JSONB).contains([ticker.upper()]))
    if tier:
        stmt = stmt.where(LlmEvaluation.tier == tier)
    if status:
        stmt = stmt.where(LlmEvaluation.status == status)
    if before:
        stmt = stmt.where(LlmEvaluation.created_at < before)
    result = await db.execute(stmt.limit(limit))
    return list(result.scalars().all())


@router.get("/{evaluation_id}", response_model=LlmEvaluationDetailOut)
async def get_evaluation(
    evaluation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LlmEvaluation:
    evaluation = await db.get(LlmEvaluation, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="LLM degerlendirmesi bulunamadi")
    return evaluation
