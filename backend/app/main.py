"""FastAPI giris noktasi.

Calistirma: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health, instruments, kap, news
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


@app.get("/")
async def root() -> dict:
    return {"service": "trade-ai", "docs": "/docs"}
