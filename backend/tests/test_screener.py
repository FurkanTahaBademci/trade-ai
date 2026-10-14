"""Hisse tarayici filtre/siralama ve API testleri (ag/DB yok)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routers import markets
from app.main import app
from app.screener.service import ScreenerFilters, screen_rows


def row(ticker, **values):
    base = {
        "ticker": ticker,
        "name": f"{ticker} A.Ş.",
        "sector": "Sanayi",
        "price_date": "2026-10-14",
        "last_price": 10.0,
        "change_1d_pct": None,
        "change_1m_pct": None,
        "change_3m_pct": None,
        "volume_try": None,
        "market_cap_try": None,
        "composite_score": None,
        "signal_label": None,
        "confidence": None,
        "fundamental_period": None,
        "fundamental_score": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "roe_pct": None,
        "revenue_yoy_pct": None,
        "net_income_yoy_pct": None,
        "net_margin_pct": None,
        "debt_to_equity": None,
        "upside_pct": None,
        "analyst_score": None,
        "analyst_count": None,
    }
    return {**base, **values}


ROWS = [
    row("AAAA", composite_score=80.0, signal_label="VERY_POSITIVE", pe_ratio=6.0, roe_pct=30.0),
    row("BBBB", composite_score=65.0, signal_label="POSITIVE", pe_ratio=14.0, sector="Banka"),
    row("CCCC", composite_score=40.0, signal_label="NEGATIVE", pe_ratio=None, roe_pct=5.0),
    row("DDDD", name="Delta Enerji", composite_score=None, pe_ratio=3.0),
]


def tickers(rows):
    return [item["ticker"] for item in rows]


def test_default_sort_is_score_desc_with_missing_scores_last():
    assert tickers(screen_rows(ROWS, ScreenerFilters())) == ["AAAA", "BBBB", "CCCC", "DDDD"]


def test_missing_values_stay_last_in_ascending_sort_too():
    result = screen_rows(ROWS, ScreenerFilters(sort="pe_ratio", order="asc"))
    assert tickers(result) == ["DDDD", "AAAA", "BBBB", "CCCC"]


def test_bound_filters_exclude_rows_without_the_value():
    # F/K'si bilinmeyen CCCC "ucuz" sayilmaz.
    assert tickers(screen_rows(ROWS, ScreenerFilters(max_pe=10))) == ["AAAA", "DDDD"]
    assert tickers(screen_rows(ROWS, ScreenerFilters(min_roe=10))) == ["AAAA"]
    assert tickers(screen_rows(ROWS, ScreenerFilters(min_score=60))) == ["AAAA", "BBBB"]


def test_text_sector_and_label_filters():
    assert tickers(screen_rows(ROWS, ScreenerFilters(query="delta"))) == ["DDDD"]
    assert tickers(screen_rows(ROWS, ScreenerFilters(query="bbb"))) == ["BBBB"]
    assert tickers(screen_rows(ROWS, ScreenerFilters(sector="banka"))) == ["BBBB"]
    positive = ScreenerFilters(labels=("VERY_POSITIVE", "POSITIVE"))
    assert tickers(screen_rows(ROWS, positive)) == ["AAAA", "BBBB"]


@pytest.fixture
def dataset(monkeypatch):
    async def fake_dataset(db):
        return {"as_of_date": "2026-10-14", "rows": ROWS}

    monkeypatch.setattr(markets, "_screener_dataset", fake_dataset)


async def test_screener_endpoint_filters_limits_and_lists_sectors(dataset):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get(
            "/api/markets/screener",
            params=[("label", "POSITIVE"), ("label", "VERY_POSITIVE"), ("limit", "1")],
        )
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 4
    assert body["matched"] == 2
    assert [item["ticker"] for item in body["rows"]] == ["AAAA"]
    assert body["sectors"] == ["Banka", "Sanayi"]


async def test_screener_rejects_unknown_label_and_sort(dataset):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        bad_label = await client.get("/api/markets/screener?label=BUY")
        bad_sort = await client.get("/api/markets/screener?sort=name;drop")
    assert bad_label.status_code == 422
    assert bad_sort.status_code == 422


async def test_screener_csv_uses_turkish_headers(dataset):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/markets/screener.csv?max_pe=10")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Hisse;Şirket;Sektör")
    assert len(text.strip().splitlines()) == 3
