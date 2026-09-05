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

    database_url: str = "postgresql+asyncpg://tradeai:tradeai@localhost:5432/tradeai"
    redis_url: str = "redis://localhost:6379/0"

    gemini_api_key: str = ""
    gemini_model_tier1: str = "gemini-3.7-flash"
    gemini_model_tier2: str = "gemini-3.1-pro"

    n8n_webhook_url: str = ""

    collector_user_agent: str = "trade-ai/0.1 (kisisel arastirma)"
    kap_rate_limit_per_sec: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
