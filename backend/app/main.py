"""FastAPI giris noktasi.

Calistirma: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    evaluations,
    fundamentals,
    health,
    institutional,
    instruments,
    kap,
    news,
    paper,
    signals,
)
from app.core.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="trade-ai API",
    description="BIST piyasa istihbarati ve paper trading backend'i",
    version="0.1.0",
    lifespan=lifespan,
)

# Faz 0'da genis CORS; dashboard domaini netlesince daraltilacak.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(kap.router)
app.include_router(news.router)
app.include_router(evaluations.router)
app.include_router(fundamentals.router)
app.include_router(institutional.analysts_router)
app.include_router(institutional.funds_router)
app.include_router(signals.router)
app.include_router(paper.router)


@app.get("/")
async def root() -> dict:
    return {"service": "trade-ai", "docs": "/docs"}
