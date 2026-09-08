"""Secili Gemini modeliyle tek ve kucuk bir baglanti testi calistirir."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.llm.service import GeminiGateway, LlmGateway


class GeminiHealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    message: str = Field(min_length=1, max_length=120)


class GeminiDiagnosticResult(BaseModel):
    ok: Literal[True] = True
    tier: Literal[1, 2]
    api_mode: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    message: str


async def test_gemini_connection(
    settings: Settings,
    *,
    tier: Literal[1, 2],
    gateway: LlmGateway | None = None,
) -> GeminiDiagnosticResult:
    """LLM batch'ini acmadan secili API/model kombinasyonunu dogrula."""
    if not settings.gemini_api_key:
        raise ValueError("Gemini API anahtari ayarlanmamis")

    model = settings.gemini_model_tier1 if tier == 1 else settings.gemini_model_tier2
    owned_gateway: GeminiGateway | None = None
    if gateway is None:
        owned_gateway = GeminiGateway(
            settings.gemini_api_key,
            api_mode=settings.gemini_api_mode,
        )
    active_gateway: LlmGateway = gateway or owned_gateway
    started = time.monotonic()
    try:
        response = await active_gateway.generate(
            model=model,
            system_instruction=(
                "Bu bir baglanti sagligi testidir. Yalnizca verilen JSON semasina uygun, "
                "kisa bir yanit ver."
            ),
            user_content="Baglanti calisiyorsa status alanini ok olarak dondur.",
            response_model=GeminiHealthPayload,
            thinking_level="low",
            max_output_tokens=256,
        )
        payload = GeminiHealthPayload.model_validate(response.data)
        latency_ms = round((time.monotonic() - started) * 1000)
        token_count = response.total_tokens if response.total_tokens is not None else "?"
        return GeminiDiagnosticResult(
            tier=tier,
            api_mode=settings.gemini_api_mode,
            model=model,
            latency_ms=latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            message=(
                f"{model} / {settings.gemini_api_mode} · {latency_ms} ms · "
                f"{token_count} token · {payload.message}"
            ),
        )
    finally:
        if owned_gateway is not None:
            await owned_gateway.aclose()
