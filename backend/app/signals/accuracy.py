"""Sinyal dogruluk raporu: gecmis sinyallerin gercek ileri getirisiyle karsilastirilmasi.

Backtest'ten (app/backtest/engine.py) farkli: portfoy/pozisyon simulasyonu
yapmaz, komisyon/kayma hesaplamaz. Sadece "yuksek skorlu/pozitif etiketli
sinyaller sonrasinda fiyat gercekten yukseldi mi" sorusuna, sabit vadelerde
(varsayilan 5/10/20 islem gunu) ileri getiri hesaplayarak cevap arar.

Baz fiyat, sinyal tarihinden SONRAKI ilk mevcut kapanistir (ayni gunun
sinyali o gunun kapanis verisini icerebilecegi icin bakis-onyargisi
onlenir) — backtest.engine'deki "sonraki mevcut kapanis" mantigiyla ayni
felsefe, ama burada tek bir pozisyon degil, tum gecmisin istatistigi
cikarilir.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

DEFAULT_HORIZONS: tuple[int, ...] = (5, 10, 20)
SIGNAL_LABELS: tuple[str, ...] = (
    "VERY_POSITIVE",
    "POSITIVE",
    "NEUTRAL",
    "NEGATIVE",
    "VERY_NEGATIVE",
)
# Yonlu etiketler icin "isabet" = ileri getirinin isaretinin beklenen yonle
# eslesmesi. NEUTRAL'in yonlu bir beklentisi yok, isabet oranina girmez.
_EXPECTED_DIRECTION: dict[str, int] = {
    "VERY_POSITIVE": 1,
    "POSITIVE": 1,
    "NEGATIVE": -1,
    "VERY_NEGATIVE": -1,
}


@dataclass(frozen=True)
class SignalObservation:
    ticker: str
    as_of_date: date
    composite_score: Decimal
    signal_label: str


@dataclass(frozen=True)
class PricePoint:
    ticker: str
    price_date: date
    close: Decimal


@dataclass(frozen=True)
class HorizonStat:
    horizon: int
    label: str
    observation_count: int
    average_return_pct: Decimal | None
    hit_rate_pct: Decimal | None


def compute_signal_accuracy(
    signals: list[SignalObservation],
    prices: list[PricePoint],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[HorizonStat]:
    by_ticker: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for price in prices:
        if price.close and price.close > 0:
            by_ticker[price.ticker].append((price.price_date, price.close))
    for rows in by_ticker.values():
        rows.sort(key=lambda row: row[0])

    returns: dict[tuple[int, str], list[Decimal]] = defaultdict(list)
    hits: dict[tuple[int, str], list[bool]] = defaultdict(list)

    for signal in signals:
        candidates = by_ticker.get(signal.ticker)
        if not candidates:
            continue
        base_index = next(
            (i for i, (row_date, _) in enumerate(candidates) if row_date > signal.as_of_date),
            None,
        )
        if base_index is None:
            continue
        _, base_close = candidates[base_index]
        if base_close <= 0:
            continue
        for horizon in horizons:
            # Bu vade icin henuz yeterli gelecek islem gunu toplanmadiysa
            # (genc bir veri setinde uzun vadeler icin normal), yalniz bu
            # vade atlanir — kisa vadeler yine de katkida bulunur.
            if base_index + horizon >= len(candidates):
                continue
            _, future_close = candidates[base_index + horizon]
            forward_return = (future_close / base_close - 1) * 100
            key = (horizon, signal.signal_label)
            returns[key].append(forward_return)
            direction = _EXPECTED_DIRECTION.get(signal.signal_label)
            if direction is not None:
                hits[key].append((forward_return > 0) == (direction > 0))

    stats: list[HorizonStat] = []
    for horizon in horizons:
        for label in SIGNAL_LABELS:
            key = (horizon, label)
            label_returns = returns.get(key, [])
            label_hits = hits.get(key, [])
            stats.append(
                HorizonStat(
                    horizon=horizon,
                    label=label,
                    observation_count=len(label_returns),
                    average_return_pct=(
                        sum(label_returns) / len(label_returns) if label_returns else None
                    ),
                    hit_rate_pct=(
                        Decimal(sum(label_hits)) / len(label_hits) * 100 if label_hits else None
                    ),
                )
            )
    return stats
