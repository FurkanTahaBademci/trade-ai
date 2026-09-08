"""Uygulama genelinde kullanilan ayarlar.

Tum degerler ortam degiskenlerinden okunur (bkz. .env.example). Yeni bir
collector veya servis ayar eklemek istediginde buraya alan ekle; kod
icinde os.environ ile dogrudan okuma yapma.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    tz: str = "Europe/Istanbul"
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1,api,testserver"

    database_url: str = "postgresql+asyncpg://tradeai:tradeai@localhost:5432/tradeai"
    redis_url: str = "redis://localhost:6379/0"

    gemini_api_key: str = ""
    gemini_api_mode: str = "interactions"
    gemini_model_tier1: str = "gemini-3.8-flash"
    gemini_model_tier2: str = "gemini-3.1-pro-preview"
    llm_enabled: bool = False
    llm_batch_size: int = 20
    llm_tier1_group_size: int = 5
    llm_max_attempts: int = 3
    llm_tier2_min_impact: int = 70
    llm_daily_input_token_limit: int = 500_000
    llm_daily_output_token_limit: int = 100_000
    llm_max_source_chars: int = 12_000

    n8n_webhook_url: str = ""
    monitoring_alert_cooldown_seconds: int = 3600
    admin_api_token: str = ""

    collector_user_agent: str = "trade-ai/0.1 (kisisel arastirma)"
    kap_rate_limit_per_sec: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
