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


class SignalHistoryPointOut(BaseModel):
    as_of_date: date
    composite_score: float
    signal_label: str
    confidence: float
    component_scores: dict


class SignalDriverOut(BaseModel):
    kind: str
    title: str
    occurred_at: str | None
    effect: float
    href: str


class SignalHistoryOut(BaseModel):
    ticker: str
    points: list[SignalHistoryPointOut]
    drivers: list[SignalDriverOut]


class SignalHorizonStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon: int
    label: str
    observation_count: int
    average_return_pct: float | None
    hit_rate_pct: float | None
    average_excess_pct: float | None = None
    beat_rate_pct: float | None = None


class SignalMoverOut(BaseModel):
    ticker: str
    composite_score: float
    previous_score: float
    change: float
    signal_label: str
    previous_label: str


class SignalMoversOut(BaseModel):
    as_of_date: date | None
    base_date: date | None
    risers: list[SignalMoverOut]
    fallers: list[SignalMoverOut]
