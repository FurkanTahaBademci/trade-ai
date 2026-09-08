"""Redis-backed calisma-zamani ayar override'lari (bkz. /sistem -> Ayarlar).

`.env` degerleri varsayilan; buradaki Redis anahtarlari varsa gecersiz kilar.
Boylece GEMINI_API_KEY / N8N_WEBHOOK_URL gibi degerler container yeniden
baslatilmadan, calisan sistemden degistirilip denenebilir. Redis bu ortamda
AOF ile kalicidir (bkz. ops/COOLIFY.md); Redis bosaltilirsa sistem sessizce
`.env` varsayilanina doner — asla kilitlenmeye yol acmaz.

Yalnizca burada listelenen (MANAGED_SETTINGS) alanlar override edilebilir;
`ADMIN_API_TOKEN` gibi erisimi koruyan degerler bilincli olarak disaridadir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.redis import get_redis

REDIS_KEY_PREFIX = "app_setting:"


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    kind: str  # "secret" | "url" | "boolean"
    field: str  # Settings uzerindeki karsilik gelen alan adi


MANAGED_SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("gemini_api_key", "Gemini API Anahtari", "secret", "gemini_api_key"),
    SettingSpec("llm_enabled", "LLM Degerlendirmesi Etkin", "boolean", "llm_enabled"),
    SettingSpec("n8n_webhook_url", "N8N Webhook URL", "url", "n8n_webhook_url"),
)
SPEC_BY_KEY = {spec.key: spec for spec in MANAGED_SETTINGS}


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


async def get_setting_statuses(*, redis: Redis | None = None) -> list[dict[str, Any]]:
    redis = redis or get_redis()
    base = get_settings()
    statuses: list[dict[str, Any]] = []
    for spec in MANAGED_SETTINGS:
        stored = await redis.hgetall(f"{REDIS_KEY_PREFIX}{spec.key}")
        env_raw = getattr(base, spec.field)
        if spec.kind == "boolean":
            # Bir boolean hep somut bir efektif degere sahiptir (true/false),
            # "unset" durumu yoktur.
            value = stored["value"] if stored else ("true" if env_raw else "false")
            source = "database" if stored else "env"
            updated_at = stored.get("updated_at") if stored else None
        elif stored:
            value, source, updated_at = stored["value"], "database", stored.get("updated_at")
        elif env_raw:
            value, source, updated_at = str(env_raw), "env", None
        else:
            value, source, updated_at = "", "unset", None
        statuses.append(
            {
                "key": spec.key,
                "label": spec.label,
                "kind": spec.kind,
                "is_set": bool(value),
                "source": source,
                "preview": value if spec.kind == "boolean" else (_mask(value) if value else None),
                "updated_at": updated_at,
            }
        )
    return statuses


async def set_setting(key: str, value: str, *, redis: Redis | None = None) -> None:
    spec = SPEC_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Bilinmeyen ayar: {key!r}")
    if not value:
        raise ValueError("Deger bos olamaz — kaldirmak icin silme islemini kullanin")
    if spec.kind == "boolean" and value not in {"true", "false"}:
        raise ValueError("boolean ayar 'true' veya 'false' olmali")
    redis = redis or get_redis()
    await redis.hset(
        f"{REDIS_KEY_PREFIX}{key}",
        mapping={"value": value, "updated_at": datetime.now(UTC).isoformat()},
    )


async def clear_setting(key: str, *, redis: Redis | None = None) -> None:
    if key not in SPEC_BY_KEY:
        raise ValueError(f"Bilinmeyen ayar: {key!r}")
    redis = redis or get_redis()
    await redis.delete(f"{REDIS_KEY_PREFIX}{key}")


async def resolve_settings(base: Settings | None = None, *, redis: Redis | None = None) -> Settings:
    """`.env` ayarlarini Redis override'lariyla birlestirip yeni bir Settings dondurur."""
    base = base or get_settings()
    redis = redis or get_redis()
    updates: dict[str, object] = {}
    for spec in MANAGED_SETTINGS:
        stored = await redis.hgetall(f"{REDIS_KEY_PREFIX}{spec.key}")
        if not stored:
            continue
        raw = stored["value"]
        updates[spec.field] = (raw == "true") if spec.kind == "boolean" else raw
    return base.model_copy(update=updates) if updates else base
