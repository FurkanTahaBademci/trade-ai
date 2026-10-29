"""Gun sonu ozeti: BIST100, paper portfoy, gunun islemleri ve skor hareketleri.

Telegram/webhook kanallarina islem gunu basina en fazla bir kez gider
(`daily_digest:<tarih>` tekrar anahtari). Hafta sonu ve tatilde son islem gunu
zaten gonderildigi icin is hicbir sey yapmaz. Varsayilan olarak kapalidir;
/sistem -> Ayarlar -> "Günlük Özet Bildirimi" ile acilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.channels import AlertMessage, configured_channels
from app.alerts.service import LABEL_TEXT, dispatch_alert
from app.core.db import session_factory
from app.core.dynamic_settings import resolve_settings
from app.core.redis import get_redis
from app.models import (
    CompositeSignalSnapshot,
    IndexDaily,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperTrade,
)
from app.signals.movers import load_signal_movers
from app.signals.service import MODEL_VERSION

logger = structlog.get_logger(__name__)

BENCHMARK_INDEX = "XU100"
EXIT_TEXT = {
    "stop_loss": "zarar-kes",
    "take_profit": "kâr-al",
    "trailing_stop": "takip eden stop",
    "signal": "skor düştü",
    "rebalance": "ağırlık azaltma",
}


@dataclass(frozen=True)
class DigestData:
    as_of: date
    index_value: float | None = None
    index_change_pct: float | None = None
    portfolio_equity: float | None = None
    portfolio_day_pct: float | None = None
    portfolio_total_pct: float | None = None
    buys: list[str] = field(default_factory=list)
    sells: list[tuple[str, str | None]] = field(default_factory=list)
    risers: list[tuple[str, float, float]] = field(default_factory=list)  # hisse, once, simdi
    fallers: list[tuple[str, float, float]] = field(default_factory=list)
    top: list[tuple[str, float, str]] = field(default_factory=list)  # hisse, skor, etiket


def _number(value: float, digits: int = 0) -> str:
    """Turkce sayi bicimi: 1.234.567,8"""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _signed_pct(value: float) -> str:
    rounded = round(value, 1)  # -0,04 "−%0,0" yazilmasin
    sign = "+" if rounded > 0 else "−" if rounded < 0 else ""
    return f"{sign}%{_number(abs(rounded), 1)}"


def _movers(items: list[tuple[str, float, float]]) -> str:
    return ", ".join(
        f"{ticker} {_number(before)}→{_number(after)}" for ticker, before, after in items
    )


def build_daily_digest(data: DigestData) -> AlertMessage:
    lines: list[str] = []
    if data.index_value is not None:
        change = (
            f" ({_signed_pct(data.index_change_pct)})" if data.index_change_pct is not None else ""
        )
        lines.append(f"BIST100: {_number(data.index_value, 2)}{change}")
    if data.portfolio_equity is not None:
        parts = [f"₺{_number(data.portfolio_equity)}"]
        if data.portfolio_day_pct is not None:
            parts.append(f"gün {_signed_pct(data.portfolio_day_pct)}")
        if data.portfolio_total_pct is not None:
            parts.append(f"toplam {_signed_pct(data.portfolio_total_pct)}")
        lines.append("Paper portföy: " + " · ".join(parts))
    trades = [f"AL {ticker}" for ticker in data.buys]
    trades += [
        f"SAT {ticker}" + (f" ({EXIT_TEXT.get(reason, reason)})" if reason else "")
        for ticker, reason in data.sells
    ]
    lines.append("İşlemler: " + (", ".join(trades) if trades else "yok"))
    if data.risers:
        lines.append(f"Skoru yükselen: {_movers(data.risers)}")
    if data.fallers:
        lines.append(f"Skoru düşen: {_movers(data.fallers)}")
    if data.top:
        lines.append(
            "En yüksek skor: "
            + ", ".join(
                f"{ticker} {_number(score)} ({LABEL_TEXT.get(label, label)})"
                for ticker, score, label in data.top
            )
        )
    lines.append("Bilgi amaçlıdır; yatırım tavsiyesi değildir.")
    return AlertMessage(
        event_type="daily_digest",
        severity="info",
        title=f"📊 BIST günlük özet · {data.as_of:%d.%m.%Y}",
        message="\n".join(lines),
        details={"as_of_date": data.as_of.isoformat()},
    )


async def collect_digest_data(session: AsyncSession) -> DigestData | None:
    index_rows = (
        await session.execute(
            select(IndexDaily.date, IndexDaily.value)
            .where(IndexDaily.index_code == BENCHMARK_INDEX)
            .order_by(IndexDaily.date.desc())
            .limit(2)
        )
    ).all()
    if not index_rows:
        return None
    as_of, index_value = index_rows[0].date, float(index_rows[0].value)
    index_change = (
        (index_value / float(index_rows[1].value) - 1) * 100
        if len(index_rows) > 1 and index_rows[1].value
        else None
    )

    equity = day_pct = total_pct = None
    buys: list[str] = []
    sells: list[tuple[str, str | None]] = []
    portfolio = await session.scalar(
        select(PaperPortfolio)
        .where(PaperPortfolio.owner_id.is_(None))
        .order_by(PaperPortfolio.id)
        .limit(1)
    )
    if portfolio is not None:
        snapshots = (
            await session.scalars(
                select(PaperPortfolioSnapshot)
                .where(
                    PaperPortfolioSnapshot.portfolio_id == portfolio.id,
                    PaperPortfolioSnapshot.snapshot_date <= as_of,
                )
                .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
                .limit(2)
            )
        ).all()
        if snapshots and snapshots[0].snapshot_date == as_of:
            equity = float(snapshots[0].total_equity)
            total_pct = float(snapshots[0].total_return_pct)
            if len(snapshots) > 1 and snapshots[1].total_equity:
                day_pct = (equity / float(snapshots[1].total_equity) - 1) * 100
        for trade in (
            await session.execute(
                select(PaperTrade.ticker, PaperTrade.side, PaperTrade.exit_reason)
                .where(PaperTrade.portfolio_id == portfolio.id, PaperTrade.trade_date == as_of)
                .order_by(PaperTrade.id)
            )
        ).all():
            if trade.side == "BUY":
                buys.append(trade.ticker)
            else:
                sells.append((trade.ticker, trade.exit_reason))

    movers = await load_signal_movers(session, days=1, limit=3)
    top_rows = (
        await session.execute(
            select(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.signal_label,
            )
            .where(
                CompositeSignalSnapshot.model_version == MODEL_VERSION,
                CompositeSignalSnapshot.as_of_date == movers.as_of_date,
            )
            .order_by(
                CompositeSignalSnapshot.composite_score.desc(), CompositeSignalSnapshot.ticker
            )
            .limit(3)
        )
    ).all()
    return DigestData(
        as_of=as_of,
        index_value=index_value,
        index_change_pct=index_change,
        portfolio_equity=equity,
        portfolio_day_pct=day_pct,
        portfolio_total_pct=total_pct,
        buys=buys,
        sells=sells,
        risers=[(row.ticker, row.previous_score, row.composite_score) for row in movers.risers],
        fallers=[(row.ticker, row.previous_score, row.composite_score) for row in movers.fallers],
        top=[(row.ticker, float(row.composite_score), row.signal_label) for row in top_rows],
    )


async def send_daily_digest(ctx: dict) -> dict[str, Any]:
    settings = await resolve_settings()
    if not settings.alerts_daily_digest_enabled:
        return {"status": "disabled"}
    if not settings.alerts_enabled or not configured_channels(settings):
        return {"status": "no_channel"}
    async with session_factory() as session:
        data = await collect_digest_data(session)
    if data is None:
        return {"status": "no_data"}
    async with httpx.AsyncClient(timeout=10) as client:
        result = await dispatch_alert(
            build_daily_digest(data),
            dedupe_key=f"daily_digest:{data.as_of.isoformat()}",
            settings=settings,
            redis=get_redis(),
            client=client,
        )
    logger.info("daily_digest", as_of=data.as_of.isoformat(), **result)
    return {
        "status": "sent" if result.get("delivered") else result.get("reason"),
        "as_of": data.as_of.isoformat(),
    }
