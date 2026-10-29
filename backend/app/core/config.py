"""Uygulama genelinde kullanilan ayarlar.

Tum degerler ortam degiskenlerinden okunur (bkz. .env.example). Yeni bir
collector veya servis ayar eklemek istediginde buraya alan ekle; kod
icinde os.environ ile dogrudan okuma yapma.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    # Docker build'de SOURCE_COMMIT build arg'indan gelir (docker-compose.yml);
    # elle ayarlanmaz. /health yanitinda surumun yaninda gosterilir.
    source_commit: str = ""
    log_level: str = "INFO"
    tz: str = "Europe/Istanbul"
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1,api,testserver"

    database_url: str = "postgresql+asyncpg://tradeai:tradeai@localhost:5432/tradeai"
    redis_url: str = "redis://localhost:6379/0"
    # Surec basina SQLAlchemy havuzu. api (API_WORKERS adet surec) ve worker ayri
    # havuz acar; toplam (API_WORKERS + 1) * (size + overflow) Postgres
    # max_connections'in (varsayilan 100) altinda kalmali.
    db_pool_size: int = 5
    db_max_overflow: int = 10

    gemini_api_key: str = ""
    # TCMB EVDS (kur, TUFE). Bos ise makro seri toplayicisi calismaz.
    evds_api_key: str = ""
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
    paper_stop_loss_pct: int = 15
    paper_take_profit_pct: int = 0
    paper_trailing_stop_pct: int = 0
    paper_max_position_weight_pct: int = 10
    paper_max_sector_weight_pct: int = 30
    paper_rebalance_enabled: bool = True
    # Kullanici portfoyleri: kisi basina portfoy ve portfoy basina bekleyen emir siniri.
    paper_max_portfolios_per_user: int = Field(default=5, ge=1, le=100)
    paper_max_pending_orders: int = Field(default=20, ge=1, le=500)
    # Kullanici backtest'i: gunluk kosu ve ayni anda kuyrukta/calisan kosu siniri.
    backtest_daily_limit_per_user: int = Field(default=10, ge=1, le=1000)
    backtest_max_active_per_user: int = Field(default=1, ge=1, le=10)

    n8n_webhook_url: str = ""
    monitoring_alert_cooldown_seconds: int = 3600
    admin_api_token: str = ""

    alerts_enabled: bool = False
    alerts_telegram_bot_token: str = ""
    alerts_telegram_chat_id: str = ""
    alerts_webhook_url: str = ""
    alerts_watch_tickers: str = ""
    alerts_high_score_threshold: int = 85
    # Islem gunu sonunda tek mesajlik ozet (app/alerts/digest.py); /sistem'den acilir.
    alerts_daily_digest_enabled: bool = False
    # Kullanicilarin kendi bildirimleri (app/alerts/personal.py): Telegram baglama,
    # anlik etiket degisimi ve gunluk ozet. Telegram icin yukaridaki bot token'i
    # kullanilir. /sistem'den kapatilabilir.
    user_alerts_enabled: bool = True

    # Kullanici hesaplari (app/auth/). "invite": yalniz davet koduyla kayit,
    # "open": herkes kayit olabilir, "closed": yeni kayit yok. /sistem'den degisir.
    registration_mode: str = "invite"
    session_ttl_days: int = Field(default=30, ge=1, le=365)
    # E-posta baglantilarinin (dogrulama, parola sifirlama) kok adresi.
    public_base_url: str = "http://localhost:3000"
    # SMTP bos ise e-posta gonderilmez; gelistirmede baglanti log'a yazilir.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    # "starttls" (587), "ssl" (465) veya "none" (yalniz yerel test sunucusu).
    smtp_security: str = "starttls"
    mail_from: str = ""
    # Google ile giris (OAuth istemcisi). Ikisi de bos ise Google dugmesi gizlenir.
    # Yonlendirme adresi: <PUBLIC_BASE_URL>/giris/google/callback
    google_client_id: str = ""
    google_client_secret: str = ""

    collector_user_agent: str = "trade-ai (acik kaynak arastirma araci)"
    kap_rate_limit_per_sec: float = 2.0

    worker_job_timeout: int = 1800
    worker_max_jobs: int = Field(default=3, ge=1, le=20)
    price_collector_chunk_size: int = 10
    price_collector_timeout: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
