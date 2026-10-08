"""Skor gecmisi 'neden bu skor?' akisi icin saf yardimcilar (LLM cagrisi yok)."""

from __future__ import annotations

from typing import Any

MAX_DRIVERS = 10


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def evaluation_effect(row: Any) -> float:
    """Skora isaretli katki tahmini (-100..100): duygu x etki x ilgi."""
    sentiment = max(-1.0, min(1.0, _num(row.sentiment_score) or 0.0))
    impact = max(0.0, min(100.0, _num(row.impact_score) or 0.0)) / 100
    relevance = max(0.0, min(100.0, _num(row.relevance_score) or 0.0)) / 100
    return round(100 * sentiment * impact * relevance, 2)


def recommendation_effect(row: Any) -> float:
    upside = _num(row.upside_pct)
    if upside is not None:
        return round(max(-100.0, min(100.0, upside)), 2)
    return {"BUY": 30.0, "SELL": -30.0}.get(row.recommendation_normalized, 0.0)


def evaluation_driver(row: Any) -> dict[str, Any]:
    kap = row.source_type == "kap"
    occurred = row.completed_at or row.created_at
    return {
        "kind": "kap" if kap else "news",
        "title": row.summary or row.event_type or ("KAP bildirimi" if kap else "Haber"),
        "occurred_at": occurred.isoformat() if occurred else None,
        "effect": evaluation_effect(row),
        "href": f"/kap/{row.source_id}" if kap else f"/haberler/{row.source_id}",
    }


def recommendation_driver(row: Any, ticker: str) -> dict[str, Any]:
    target = _num(row.target_price)
    suffix = f" · hedef {target:g}" if target is not None else ""
    return {
        "kind": "analyst",
        "title": f"{row.institution}: {row.recommendation_raw}{suffix}",
        "occurred_at": row.recommendation_date.isoformat(),
        "effect": recommendation_effect(row),
        "href": f"/piyasalar/{ticker}#gorusler",
    }


def rank_drivers(drivers: list[dict[str, Any]], limit: int = MAX_DRIVERS) -> list[dict[str, Any]]:
    """En etkili `limit` ogeyi secer ve yeniden eskiye kronolojik dizer."""
    strongest = sorted(drivers, key=lambda item: abs(item["effect"]), reverse=True)[:limit]
    return sorted(strongest, key=lambda item: item["occurred_at"] or "", reverse=True)
