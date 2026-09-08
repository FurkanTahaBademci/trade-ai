"""Gemini baglanti testinin agsiz birim testleri."""

import pytest

from app.core.config import Settings
from app.llm.diagnostics import test_gemini_connection as run_gemini_connection
from app.llm.service import GatewayResponse


class FakeGateway:
    def __init__(self):
        self.request = None

    async def generate(self, **kwargs):
        self.request = kwargs
        return GatewayResponse(
            data={"status": "ok", "message": "Baglanti hazir."},
            raw_text='{"status":"ok","message":"Baglanti hazir."}',
            input_tokens=8,
            output_tokens=12,
            total_tokens=20,
        )


async def test_connection_uses_selected_tier_without_enabling_batch():
    gateway = FakeGateway()
    settings = Settings(
        gemini_api_key="test-key",
        gemini_api_mode="interactions",
        gemini_model_tier1="flash-model",
        gemini_model_tier2="pro-model",
        llm_enabled=False,
    )

    result = await run_gemini_connection(settings, tier=2, gateway=gateway)

    assert result.model == "pro-model"
    assert result.api_mode == "interactions"
    assert result.total_tokens == 20
    assert "20 token" in result.message
    assert gateway.request["model"] == "pro-model"
    assert gateway.request["max_output_tokens"] == 256


async def test_connection_rejects_missing_api_key_before_call():
    with pytest.raises(ValueError, match="anahtari ayarlanmamis"):
        await run_gemini_connection(Settings(gemini_api_key=""), tier=1, gateway=FakeGateway())
