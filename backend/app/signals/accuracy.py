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

Dusen bir piyasada her etiketin mutlak getirisi negatif cikar ve yon isabeti
yaniltir. Bu yuzden BIST100 serisi verildiginde ayni tarih araligindaki
endeks getirisi de cikarilir: `average_excess_pct` ve `beat_rate_pct`
(endeksi yenme orani) asil degerlendirme olcusudur.
"""

from __future__ import annotations

from bisect import bisect_right
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
    average_excess_pct: Decimal | None = None
    beat_rate_pct: Decimal | None = None


def _value_at_or_before(
    dates: list[date], values: list[Decimal], target: date
) -> Decimal | None:
    index = bisect_right(dates, target) - 1
    return values[index] if index >= 0 else None


def compute_signal_accuracy(
    signals: list[SignalObservation],
    prices: list[PricePoint],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    benchmark: list[tuple[date, Decimal]] | None = None,
) -> list[HorizonStat]:
    bench_rows = sorted(row for row in benchmark or [] if row[1] and row[1] > 0)
    bench_dates = [row_date for row_date, _ in bench_rows]
    bench_values = [value for _, value in bench_rows]
    by_ticker: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for price in prices:
        if price.close and price.close > 0:
            by_ticker[price.ticker].append((price.price_date, price.close))
    for rows in by_ticker.values():
        rows.sort(key=lambda row: row[0])
    dates_by_ticker = {
        ticker: [row_date for row_date, _ in rows] for ticker, rows in by_ticker.items()
    }

    returns: dict[tuple[int, str], list[Decimal]] = defaultdict(list)
    hits: dict[tuple[int, str], list[bool]] = defaultdict(list)
    excess: dict[tuple[int, str], list[Decimal]] = defaultdict(list)
    beats: dict[tuple[int, str], list[bool]] = defaultdict(list)

    for signal in signals:
        candidates = by_ticker.get(signal.ticker)
        if not candidates:
            continue
        # Binary search avoids rescanning a ticker's entire price history for
        # every daily signal. This is material on a cold accuracy-cache fill.
        base_index = bisect_right(dates_by_ticker[signal.ticker], signal.as_of_date)
        if base_index >= len(candidates):
            continue
        base_date, base_close = candidates[base_index]
        if base_close <= 0:
            continue
        for horizon in horizons:
            # Bu vade icin henuz yeterli gelecek islem gunu toplanmadiysa
            # (genc bir veri setinde uzun vadeler icin normal), yalniz bu
            # vade atlanir — kisa vadeler yine de katkida bulunur.
            if base_index + horizon >= len(candidates):
                continue
            future_date, future_close = candidates[base_index + horizon]
            forward_return = (future_close / base_close - 1) * 100
            key = (horizon, signal.signal_label)
            returns[key].append(forward_return)
            direction = _EXPECTED_DIRECTION.get(signal.signal_label)
            if direction is not None:
                hits[key].append((forward_return > 0) == (direction > 0))
            bench_base = _value_at_or_before(bench_dates, bench_values, base_date)
            bench_future = _value_at_or_before(bench_dates, bench_values, future_date)
            if bench_base and bench_future:
                excess_return = forward_return - (bench_future / bench_base - 1) * 100
                excess[key].append(excess_return)
                if direction is not None:
                    beats[key].append((excess_return > 0) == (direction > 0))

    stats: list[HorizonStat] = []
    for horizon in horizons:
        for label in SIGNAL_LABELS:
            key = (horizon, label)
            label_returns = returns.get(key, [])
            label_hits = hits.get(key, [])
            label_excess = excess.get(key, [])
            label_beats = beats.get(key, [])
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
                    average_excess_pct=(
                        sum(label_excess) / len(label_excess) if label_excess else None
                    ),
                    beat_rate_pct=(
                        Decimal(sum(label_beats)) / len(label_beats) * 100 if label_beats else None
                    ),
                )
            )
    return stats
