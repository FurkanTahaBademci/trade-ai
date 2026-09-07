"""TCMB para politikasi API semalari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MonetaryPolicyDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_no: str
    decision_date: date
    status: str
    decision_type: str
    policy_rate: float | None
    previous_policy_rate: float | None
    change_bps: int | None
    lending_rate: float | None
    borrowing_rate: float | None
    title: str
    summary: str | None
    guidance: str | None
    source_url: str | None
    market_impact: dict
    created_at: datetime
    updated_at: datetime
