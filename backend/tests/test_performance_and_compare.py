import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def test_compare_and_optimized_routes_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/markets/compare" in paths
    assert "/api/markets/heatmap" in paths
    assert "/api/signals/accuracy" in paths
    assert "/api/instruments" in paths


@pytest.mark.asyncio
async def test_compare_endpoint_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        # 1. Tek hisse ile istek reddedilmeli
        resp = await client.get("/api/markets/compare?tickers=THYAO")
        assert resp.status_code == 400
        assert "en az 2" in resp.json()["detail"]

        # 2. Bos hisse ile istek reddedilmeli
        resp_empty = await client.get("/api/markets/compare?tickers=")
        assert resp_empty.status_code == 400
