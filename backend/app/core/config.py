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
    llm_batch_size: int = 50
    llm_tier1_group_size: int = 10
    llm_max_attempts: int = 3
    llm_tier2_min_impact: int = 70
    llm_daily_input_token_limit: int = 0
    llm_daily_output_token_limit: int = 0
    llm_max_source_chars: int = 12_000

    # Paper portfoy risk kurallari (yuzde; 0 = kapali). Varsayilanlar mevcut davranisi korur.
    paper_stop_loss_pct: int = 0
    paper_take_profit_pct: int = 0
    paper_trailing_stop_pct: int = 0
    paper_max_position_weight_pct: int = 10
    paper_max_sector_weight_pct: int = 0
    paper_rebalance_enabled: bool = False

    n8n_webhook_url: str = ""
    monitoring_alert_cooldown_seconds: int = 3600
    admin_api_token: str = ""

    alerts_enabled: bool = False
    alerts_telegram_bot_token: str = ""
    alerts_telegram_chat_id: str = ""
    alerts_webhook_url: str = ""
    alerts_watch_tickers: str = ""
    alerts_high_score_threshold: int = 85

    collector_user_agent: str = "trade-ai (acik kaynak arastirma araci)"
    kap_rate_limit_per_sec: float = 2.0

    worker_job_timeout: int = 1800
    price_collector_chunk_size: int = 10
    price_collector_timeout: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
