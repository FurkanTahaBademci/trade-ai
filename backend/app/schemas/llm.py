"""LLM yapilandirilmis cikti ve API semalari."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventType = Literal[
    "earnings",
    "corporate_action",
    "contract",
    "financing",
    "governance",
    "regulatory",
    "macro",
    "market",
    "legal",
    "operations",
    "other",
]
TimeHorizon = Literal["intraday", "short", "medium", "long", "unclear"]
ExpectedDirection = Literal["positive", "negative", "neutral", "mixed"]

_TICKER_RE = re.compile(r"^[A-Z0-9]{2,16}$")


class _AnalysisBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool
    relevance_score: int = Field(ge=0, le=100)
    sentiment_score: float = Field(ge=-1, le=1)
    impact_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    event_type: EventType
    time_horizon: TimeHorizon
    summary: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=1200)
    ticker_codes: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("ticker_codes")
    @classmethod
    def normalize_ticker_codes(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            ticker = value.strip().upper()
            if not _TICKER_RE.fullmatch(ticker):
                raise ValueError(f"Gecersiz ticker kodu: {value!r}")
            if ticker not in normalized:
                normalized.append(ticker)
        return normalized


class LlmTier1Result(_AnalysisBase):
    requires_deep_analysis: bool


class LlmTier2Result(_AnalysisBase):
    expected_direction: ExpectedDirection
    thesis: str = Field(min_length=1, max_length=1600)
    catalysts: list[str] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=8)


class LlmEvaluationListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_id: int
    prompt_version: str
    tier: int
    provider: str
    model: str
    status: str
    attempt_count: int
    ticker_codes: list[str]
    relevance_score: int | None
    sentiment_score: float | None
    impact_score: int | None
    confidence: float | None
    event_type: str | None
    time_horizon: str | None
    summary: str | None
    requires_tier2: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    completed_at: datetime | None
    created_at: datetime


class LlmEvaluationDetailOut(LlmEvaluationListOut):
    evaluation_key: str
    parent_evaluation_key: str | None
    content_hash: str
    input_document: dict
    rationale: str | None
    result: dict | None
    raw_response: str | None
    error_text: str | None
    started_at: datetime
    updated_at: datetime
