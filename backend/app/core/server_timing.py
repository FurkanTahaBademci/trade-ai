"""Yanıtlara `Server-Timing: app;dur=<ms>` başlığı ekleyen ASGI middleware.

Süre, isteğin uygulamaya girişinden yanıt başlıklarının gönderilmesine kadardır
(JSON yanıtlarda gövde bu anda hazırdır). Web sunucusu bu değeri kendi ölçtüğü
API bekleme süresiyle karşılaştırır; arada kalan ağ, uvicorn kuyruğu ve
event-loop beklemesidir (yönetici /sistem sayfası).
"""

from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ServerTimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = perf_counter()

        async def send_with_timing(message: Message) -> None:
            if message["type"] == "http.response.start":
                duration = (perf_counter() - started) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"server-timing", f"app;dur={duration:.1f}".encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_timing)
