"""Sunucu tarafi izleme listesi ucu."""

from fastapi.testclient import TestClient

from app.api.routers.watchlist import normalize_tickers
from app.main import app


def test_normalize_uppercases_dedupes_and_drops_invalid():
    assert normalize_tickers([" thyao", "THYAO", "asels", "", "BAD-CODE", "x" * 20]) == [
        "THYAO",
        "ASELS",
    ]


def test_watchlist_requires_admin_token(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "admin_api_token", "secret")
    client = TestClient(app)
    assert client.get("/api/watchlist").status_code == 401
    assert client.put("/api/watchlist", json={"tickers": ["THYAO"]}).status_code == 401
