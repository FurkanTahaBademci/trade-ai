"""Tum collector'larin turedigi ortak taban.

Vibe coding kurali #3 (.claude/CLAUDE.md): retry, rate-limit ve saglik
raporlama burada tek yerde dogru yazilir; her collector bunu miras alir,
ayni hata yonetimini tekrar tekrar yazmaz.

Kullanim (Faz 2+ ornegi):

    class KapCollector(BaseCollector):
        name = "kap"

        async def run(self) -> dict:
            data = await self.get_json("https://...", headers={...})
            ...
            return {"new": 5, "updated": 0}

    async with KapCollector() as c:
        result = await c.run_tracked()  # basari/hata Redis'e yazilir
"""

from __future__ import annotations

import time
from datetime import UTC
from types import TracebackType
from typing import Self

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.redis import get_redis

settings = get_settings()


class CollectorError(Exception):
    """Bir collector calisirken olusan, yeniden denenebilir hata."""


class BaseCollector:
    """Tum collector'lar (KAP, haber, fiyat, TEFAS, ...) bundan turer.

    Alt siniflar sadece `name` sinif degiskenini ve `async def run(self)`
    metodunu tanimlar. HTTP client, retry ve saglik takibi burada hazir.
    """

    name: str = "base"

    def __init__(self, *, rate_limit_per_sec: float | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._rate_limit_per_sec = rate_limit_per_sec
        self._last_request_at: float = 0.0

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.collector_user_agent},
            timeout=30,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                f"{self.name} collector 'async with' disinda kullanildi — client henuz acilmadi."
            )
        return self._client

    @property
    def log(self) -> structlog.BoundLogger:
        return structlog.get_logger(self.name)

    async def _throttle(self) -> None:
        """Basit sabit-araliki rate limit (orn. KAP icin 2 req/s)."""
        if not self._rate_limit_per_sec:
            return
        min_interval = 1.0 / self._rate_limit_per_sec
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_interval:
            import asyncio

            await asyncio.sleep(min_interval - elapsed)
        self._last_request_at = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def get_json(self, url: str, **kwargs) -> dict | list:
        await self._throttle()
        resp = await self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def get_bytes(self, url: str, **kwargs) -> bytes:
        """Ikili dosya indir (KAP PDF eki gibi); JSON retry politikasini kullan."""
        await self._throttle()
        resp = await self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.content

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def post_json(self, url: str, json: dict, **kwargs) -> dict | list:
        await self._throttle()
        resp = await self.client.post(url, json=json, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def run(self) -> dict:
        """Alt siniflarin doldurmasi gereken asil is. Bir ozet dict doner."""
        raise NotImplementedError

    async def run_tracked(self) -> dict:
        """`run()`'i calistirir, sonucu Redis'e yazar (Faz 10 saglik takibi).

        Basarili calisma: `collector:{name}:last_success` -> ISO zaman damgasi
        Basarisiz calisma: `collector:{name}:last_error` -> hata mesaji + zaman
        Bu anahtarlar `/health/detailed` tarafindan okunacak (Faz 10).
        """
        redis = get_redis()
        from datetime import datetime

        try:
            result = await self.run()
            await redis.set(f"collector:{self.name}:last_success", datetime.now(UTC).isoformat())
            self.log.info("collector_run_ok", **(result or {}))
            return result
        except Exception as exc:
            await redis.set(
                f"collector:{self.name}:last_error",
                f"{datetime.now(UTC).isoformat()} | {exc!r}",
            )
            self.log.error("collector_run_failed", error=str(exc))
            raise
