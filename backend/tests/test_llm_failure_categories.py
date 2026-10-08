import pytest

from app.api.routers.system import classify_llm_failure


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Rate limit exceeded (limit: 500 requests per day on Free Tier)", "daily_quota"),
        ("429 RESOURCE_EXHAUSTED. Please retry in 120s", "rate_limit"),
        ("model is experiencing high demand", "provider_unavailable"),
        ("Gemini API gecici olarak HTTP 403 HTML yaniti dondurdu", "provider_unavailable"),
        ("invalid JSON returned for structured output schema", "invalid_response"),
        ("unknown model", "other"),
        (None, "other"),
    ],
)
def test_llm_failure_category_is_safe_and_deterministic(message, expected):
    assert classify_llm_failure(message) == expected
