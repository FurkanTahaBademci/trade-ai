"""Redis tabanli calisma-zamani ayar override testleri (agsiz, gercek Redis'siz)."""

import pytest

from app.api.routers.system import _estimated_requests
from app.core.config import Settings
from app.core.dynamic_settings import (
    clear_setting,
    get_setting_statuses,
    resolve_settings,
    set_setting,
)
from app.main import app


def test_settings_and_system_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/settings" in paths
    assert "/api/settings/{key}" in paths
    assert "/api/settings/gemini/test" in paths
    assert "/api/system/llm" in paths
    assert "/api/system/storage" in paths


def test_llm_request_estimate_uses_configured_group_size():
    assert _estimated_requests(0, 5) == 0
    assert _estimated_requests(1, 5) == 1
    assert _estimated_requests(10, 5) == 2
    assert _estimated_requests(11, 5) == 3
    assert _estimated_requests(3, 0) == 3


class FakeRedis:
    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def delete(self, key):
        self.hashes.pop(key, None)


def _base_settings(**overrides) -> Settings:
    fields = {"gemini_api_key": "", "llm_enabled": False, "n8n_webhook_url": "", **overrides}
    return Settings(**fields)


async def test_status_reports_env_source_when_no_override_stored():
    redis = FakeRedis()
    statuses = await get_setting_statuses(redis=redis)

    gemini = next(item for item in statuses if item["key"] == "gemini_api_key")
    assert gemini["is_set"] is False
    assert gemini["source"] in {"env", "unset"}


async def test_set_and_read_back_masks_the_value():
    redis = FakeRedis()
    await set_setting("gemini_api_key", "sk-abcdefgh1234", redis=redis)

    statuses = await get_setting_statuses(redis=redis)
    gemini = next(item for item in statuses if item["key"] == "gemini_api_key")

    assert gemini["source"] == "database"
    assert gemini["is_set"] is True
    assert gemini["preview"] == "••••1234"
    assert "sk-abcdefgh1234" not in str(gemini)


async def test_set_setting_rejects_unknown_key():
    with pytest.raises(ValueError, match="Bilinmeyen ayar"):
        await set_setting("admin_api_token", "x", redis=FakeRedis())


async def test_set_setting_rejects_empty_value():
    with pytest.raises(ValueError, match="bos olamaz"):
        await set_setting("gemini_api_key", "", redis=FakeRedis())


async def test_boolean_setting_only_accepts_true_or_false():
    redis = FakeRedis()
    with pytest.raises(ValueError, match="boolean"):
        await set_setting("llm_enabled", "yes", redis=redis)

    await set_setting("llm_enabled", "true", redis=redis)
    statuses = await get_setting_statuses(redis=redis)
    llm = next(item for item in statuses if item["key"] == "llm_enabled")
    assert llm["preview"] == "true"
    assert llm["source"] == "database"


async def test_gemini_api_and_model_choices_are_exposed_and_validated():
    redis = FakeRedis()
    statuses = await get_setting_statuses(redis=redis)
    api_mode = next(item for item in statuses if item["key"] == "gemini_api_mode")
    tier1 = next(item for item in statuses if item["key"] == "gemini_model_tier1")
    group_size = next(item for item in statuses if item["key"] == "llm_tier1_group_size")

    assert api_mode["preview"] == "interactions"
    assert {item["value"] for item in api_mode["choices"]} == {
        "interactions",
        "generate_content",
    }
    assert tier1["preview"] == "gemini-3.8-flash"
    assert any(item["value"] == "gemini-3.1-pro-preview" for item in tier1["choices"])
    assert group_size["preview"] == "5"
    assert {item["value"] for item in group_size["choices"]} == {"1", "3", "5"}

    with pytest.raises(ValueError, match="Desteklenmeyen secim"):
        await set_setting("gemini_api_mode", "openai", redis=redis)
    with pytest.raises(ValueError, match="Desteklenmeyen secim"):
        await set_setting("gemini_model_tier1", "uydurma-model", redis=redis)


async def test_clear_setting_reverts_to_env_default():
    redis = FakeRedis()
    await set_setting("gemini_api_key", "sk-override1234", redis=redis)
    await clear_setting("gemini_api_key", redis=redis)

    statuses = await get_setting_statuses(redis=redis)
    gemini = next(item for item in statuses if item["key"] == "gemini_api_key")
    assert gemini["source"] in {"env", "unset"}


async def test_resolve_settings_merges_database_override_over_env():
    redis = FakeRedis()
    await set_setting("gemini_api_key", "sk-override1234", redis=redis)
    await set_setting("llm_enabled", "true", redis=redis)
    await set_setting("gemini_api_mode", "generate_content", redis=redis)
    await set_setting("gemini_model_tier1", "gemini-3.7-flash", redis=redis)
    await set_setting("llm_tier1_group_size", "3", redis=redis)
    base = _base_settings(gemini_api_key="sk-env-default")

    resolved = await resolve_settings(base, redis=redis)

    assert resolved.gemini_api_key == "sk-override1234"
    assert resolved.llm_enabled is True
    assert resolved.gemini_api_mode == "generate_content"
    assert resolved.gemini_model_tier1 == "gemini-3.7-flash"
    assert resolved.llm_tier1_group_size == 3
    assert resolved.n8n_webhook_url == ""


async def test_resolve_settings_returns_env_values_when_nothing_stored():
    base = _base_settings(gemini_api_key="sk-env-only")

    resolved = await resolve_settings(base, redis=FakeRedis())

    assert resolved.gemini_api_key == "sk-env-only"
    assert resolved.llm_enabled is False
