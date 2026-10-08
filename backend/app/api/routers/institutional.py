"""Analist gorusu, konsensus ve fon akimi endpoint'leri."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import AnalystConsensus, AnalystRecommendation, FundFlowAggregate, FundSnapshot
from app.schemas.institutional import (
    AnalystConsensusOut,
    AnalystRecommendationOut,
    FundFlowAggregateOut,
    FundSnapshotOut,
)

analysts_router = APIRouter(prefix="/api/analysts", tags=["analysts"])
funds_router = APIRouter(prefix="/api/funds", tags=["funds"])


class RecommendationValue(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    REVIEW = "REVIEW"


class FundKind(StrEnum):
    YAT = "YAT"
    EMK = "EMK"
    BYF = "BYF"
    GYF = "GYF"
    GSYF = "GSYF"


@analysts_router.get("/{ticker}/recommendations", response_model=list[AnalystRecommendationOut])
async def list_analyst_recommendations(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    institution: Annotated[str | None, Query(max_length=128)] = None,
    recommendation: Annotated[RecommendationValue | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AnalystRecommendation]:
    stmt = select(AnalystRecommendation).where(AnalystRecommendation.ticker == ticker.upper())
    if institution:
        stmt = stmt.where(AnalystRecommendation.institution == institution)
    if recommendation:
        stmt = stmt.where(AnalystRecommendation.recommendation_normalized == recommendation)
    stmt = stmt.order_by(
        AnalystRecommendation.recommendation_date.desc(), AnalystRecommendation.id.desc()
    )
    return list((await db.scalars(stmt.limit(limit))).all())


@analysts_router.get("/{ticker}/consensus", response_model=list[AnalystConsensusOut])
async def list_analyst_consensus(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[AnalystConsensus]:
    stmt = (
        select(AnalystConsensus)
        .where(AnalystConsensus.ticker == ticker.upper())
        .order_by(AnalystConsensus.as_of_date.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


@funds_router.get("/flows", response_model=list[FundFlowAggregateOut])
async def list_fund_flow_aggregates(
    db: Annotated[AsyncSession, Depends(get_db)],
    fund_kind: Annotated[FundKind, Query()] = FundKind.YAT,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[FundFlowAggregate]:
    stmt = select(FundFlowAggregate).where(FundFlowAggregate.fund_kind == fund_kind)
    if start:
        stmt = stmt.where(FundFlowAggregate.date >= start)
    if end:
        stmt = stmt.where(FundFlowAggregate.date <= end)
    stmt = stmt.order_by(FundFlowAggregate.date.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


@funds_router.get("/{fund_code}/snapshots", response_model=list[FundSnapshotOut])
async def list_fund_snapshots(
    fund_code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    fund_kind: Annotated[FundKind, Query()] = FundKind.YAT,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 90,
) -> list[FundSnapshot]:
    stmt = select(FundSnapshot).where(
        FundSnapshot.fund_kind == fund_kind,
        FundSnapshot.fund_code == fund_code.upper(),
    )
    if start:
        stmt = stmt.where(FundSnapshot.date >= start)
    if end:
        stmt = stmt.where(FundSnapshot.date <= end)
    stmt = stmt.order_by(FundSnapshot.date.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())
