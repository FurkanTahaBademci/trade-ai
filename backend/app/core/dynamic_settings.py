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
    kind: str  # "secret" | "url" | "boolean" | "choice" | "text"
    field: str  # Settings uzerindeki karsilik gelen alan adi
    choices: tuple[tuple[str, str], ...] = ()


GEMINI_MODEL_CHOICES: tuple[tuple[str, str], ...] = (
    ("gemini-3.8-flash", "Gemini 3.8 Flash · GA · önerilen"),
    ("gemini-3.7-flash", "Gemini 3.7 Flash · GA"),
    ("gemini-3.6-flash", "Gemini 3.6 Flash · GA"),
    ("gemini-3.5-flash", "Gemini 3.5 Flash · GA"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite · düşük maliyet"),
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro · Preview · derin analiz"),
)
GEMINI_API_CHOICES: tuple[tuple[str, str], ...] = (
    ("interactions", "Interactions API · SSE streaming · önerilen"),
    ("generate_content", "GenerateContent API · uyumluluk modu"),
)
TIER1_GROUP_SIZE_CHOICES: tuple[tuple[str, str], ...] = (
    ("1", "Tekli · en kolay izolasyon"),
    ("3", "3 kayıt / istek"),
    ("5", "5 kayıt / istek"),
    ("10", "10 kayıt / istek · önerilen"),
    ("15", "15 kayıt / istek"),
    ("20", "20 kayıt / istek · maksimum"),
)
LLM_OUTPUT_TOKEN_LIMIT_CHOICES: tuple[tuple[str, str], ...] = (
    ("0", "0 (Sınırsız) · Tokenı sonuna kadar kullan · önerilen"),
    ("1000000", "1.000.000 token (~4.500 haber)"),
    ("5000000", "5.000.000 token (~22.000 haber)"),
    ("10000000", "10.000.000 token (~45.000 haber)"),
    ("50000000", "50.000.000 token (~225.000 haber)"),
)
LLM_BATCH_SIZE_CHOICES: tuple[tuple[str, str], ...] = (
    ("20", "20 kayıt / döngü"),
    ("50", "50 kayıt / döngü · önerilen"),
    ("100", "100 kayıt / döngü · hızlı eritme"),
    ("200", "200 kayıt / döngü · agresif"),
)
ALERT_SCORE_CHOICES: tuple[tuple[str, str], ...] = (
    ("75", "75 · çok olumlu bandın başı"),
    ("80", "80 puan"),
    ("85", "85 puan · önerilen"),
    ("90", "90 puan · yalnız en güçlüler"),
)


def _pct_choices(
    values: tuple[int, ...], off_label: str, recommended: int | None = None
) -> tuple[tuple[str, str], ...]:
    def label(v: int) -> str:
        text = off_label if v == 0 else f"%{v}"
        return f"{text} · önerilen" if v == recommended else text

    return tuple((str(v), label(v)) for v in values)


PAPER_INT_FIELDS = {
    "paper_stop_loss_pct",
    "paper_take_profit_pct",
    "paper_trailing_stop_pct",
    "paper_max_position_weight_pct",
    "paper_max_sector_weight_pct",
}


MANAGED_SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("gemini_api_key", "Gemini API Anahtari", "secret", "gemini_api_key"),
    SettingSpec(
        "gemini_api_mode",
        "Gemini İstek API'si",
        "choice",
        "gemini_api_mode",
        GEMINI_API_CHOICES,
    ),
    SettingSpec(
        "gemini_model_tier1",
        "Gemini Tier 1 Modeli",
        "choice",
        "gemini_model_tier1",
        GEMINI_MODEL_CHOICES,
    ),
    SettingSpec(
        "gemini_model_tier2",
        "Gemini Tier 2 Modeli",
        "choice",
        "gemini_model_tier2",
        GEMINI_MODEL_CHOICES,
    ),
    SettingSpec(
        "llm_tier1_group_size",
        "Tier 1 İstek Grup Boyutu",
        "choice",
        "llm_tier1_group_size",
        TIER1_GROUP_SIZE_CHOICES,
    ),
    SettingSpec(
        "llm_daily_output_token_limit",
        "Günlük Çıktı Token Bütçesi",
        "choice",
        "llm_daily_output_token_limit",
        LLM_OUTPUT_TOKEN_LIMIT_CHOICES,
    ),
    SettingSpec(
        "llm_batch_size",
        "Döngü Başına İşlenen Kayıt (Batch)",
        "choice",
        "llm_batch_size",
        LLM_BATCH_SIZE_CHOICES,
    ),
    SettingSpec(
        "paper_stop_loss_pct",
        "Paper Zarar-Kes",
        "choice",
        "paper_stop_loss_pct",
        _pct_choices((0, 5, 8, 10, 15, 20), "Kapalı", recommended=15),
    ),
    SettingSpec(
        "paper_take_profit_pct",
        "Paper Kâr-Al",
        "choice",
        "paper_take_profit_pct",
        _pct_choices((0, 10, 20, 30, 50), "Kapalı", recommended=0),
    ),
    SettingSpec(
        "paper_trailing_stop_pct",
        "Paper Trailing Stop",
        "choice",
        "paper_trailing_stop_pct",
        _pct_choices((0, 5, 8, 10, 15), "Kapalı", recommended=0),
    ),
    SettingSpec(
        "paper_max_position_weight_pct",
        "Paper Tek Pozisyon Maks. Ağırlık",
        "choice",
        "paper_max_position_weight_pct",
        _pct_choices((5, 8, 10, 15, 20), "", recommended=10),
    ),
    SettingSpec(
        "paper_max_sector_weight_pct",
        "Paper Sektör Konsantrasyon Limiti",
        "choice",
        "paper_max_sector_weight_pct",
        _pct_choices((0, 20, 30, 40, 50), "Sınırsız", recommended=30),
    ),
    SettingSpec(
        "paper_rebalance_enabled",
        "Paper Rebalance (tavanı aşanı kırp)",
        "boolean",
        "paper_rebalance_enabled",
    ),
    SettingSpec("llm_enabled", "LLM Degerlendirmesi Etkin", "boolean", "llm_enabled"),
    SettingSpec("n8n_webhook_url", "N8N Webhook URL", "url", "n8n_webhook_url"),
    SettingSpec("alerts_enabled", "Bildirimler Etkin", "boolean", "alerts_enabled"),
    SettingSpec(
        "alerts_telegram_bot_token",
        "Telegram Bot Token",
        "secret",
        "alerts_telegram_bot_token",
    ),
    SettingSpec(
        "alerts_telegram_chat_id", "Telegram Chat ID", "secret", "alerts_telegram_chat_id"
    ),
    SettingSpec("alerts_webhook_url", "Bildirim Webhook URL", "url", "alerts_webhook_url"),
    SettingSpec(
        "alerts_watch_tickers",
        "Ek İzleme Listesi (virgülle ayrılmış)",
        "text",
        "alerts_watch_tickers",
    ),
    SettingSpec(
        "alerts_high_score_threshold",
        "Yüksek Skor Bildirim Eşiği",
        "choice",
        "alerts_high_score_threshold",
        ALERT_SCORE_CHOICES,
    ),
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
        elif env_raw is not None and str(env_raw) != "":
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
                "preview": (
                    value
                    if spec.kind in {"boolean", "choice", "text"}
                    else (_mask(value) if value else None)
                ),
                "choices": [
                    {"value": choice_value, "label": choice_label}
                    for choice_value, choice_label in spec.choices
                ],
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
    if spec.kind == "choice" and value not in {item[0] for item in spec.choices}:
        raise ValueError(f"Desteklenmeyen secim: {value!r}")
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
        if spec.kind == "boolean":
            updates[spec.field] = raw == "true"
        elif spec.field in PAPER_INT_FIELDS | {
            "llm_tier1_group_size",
            "llm_daily_output_token_limit",
            "llm_batch_size",
            "alerts_high_score_threshold",
        }:
            updates[spec.field] = int(raw)
        else:
            updates[spec.field] = raw
    return base.model_copy(update=updates) if updates else base
