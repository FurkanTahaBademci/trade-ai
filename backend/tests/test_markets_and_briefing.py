"""Market Heatmap ve AI Briefing API rota sozlesmesi testleri."""

from app.main import app


def test_market_and_briefing_routes_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/markets/heatmap" in paths
    assert "/api/ai/briefing" in paths
