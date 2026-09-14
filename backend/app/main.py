"""FastAPI giris noktasi.

Calistirma: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.routers import (
    backtests,
    evaluations,
    fundamentals,
    health,
    index_prices,
    institutional,
    instruments,
    kap,
    macro,
    news,
    paper,
    schedules,
    signals,
    system,
)
from app.api.routers import (
    settings as settings_router,
)
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="trade-ai API",
    description="BIST piyasa istihbarati ve paper trading backend'i",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)
allowed_hosts = [item.strip() for item in settings.allowed_hosts.split(",") if item.strip()]
for default_host in ("localhost", "127.0.0.1", "api"):
    if default_host not in allowed_hosts:
        allowed_hosts.append(default_host)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)

app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(index_prices.router)
app.include_router(kap.router)
app.include_router(news.router)
app.include_router(evaluations.router)
app.include_router(fundamentals.router)
app.include_router(institutional.analysts_router)
app.include_router(institutional.funds_router)
app.include_router(signals.router)
app.include_router(backtests.router)
app.include_router(paper.router)
app.include_router(macro.router)
app.include_router(schedules.router)
app.include_router(settings_router.router)
app.include_router(system.router)


@app.get("/")
async def root() -> dict:
    return {"service": "trade-ai", "docs": "/docs"}
