"""Bilesik skor API ciktilari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CompositeSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    as_of_date: date
    model_version: str
    composite_score: float
    signal_label: str
    confidence: float
    coverage_count: int
    component_scores: dict
    component_weights: dict
    evidence: dict
    computed_at: datetime
