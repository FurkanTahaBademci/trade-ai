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

Ayni hisse icin ayni giris kapanisina dusen sinyallerden (cuma, cumartesi ve
pazar skorlari pazartesi kapanisindan girer) yalniz en guncel olani sayilir;
aksi halde hafta sonlari ayni gozlem uc kez sayilip orneklem sisirdi.

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


def _entries(
    signals: list, dates_by_ticker: dict[str, list[date]]
) -> list[tuple[SignalObservation, int]]:
    """(sinyal, giris kapanisi indeksi); ayni hisse ve giris gunu icin en guncel sinyal.

    Ikili arama her gunluk sinyal icin hissenin tum fiyat gecmisini taramayi onler.
    """
    latest: dict[tuple[str, int], SignalObservation] = {}
    for signal in signals:
        dates = dates_by_ticker.get(signal.ticker)
        if not dates:
            continue
        base_index = bisect_right(dates, signal.as_of_date)
        if base_index >= len(dates):
            continue
        key = (signal.ticker, base_index)
        if key not in latest or latest[key].as_of_date < signal.as_of_date:
            latest[key] = signal
    return [(signal, index) for (_, index), signal in latest.items()]


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

    for signal, base_index in _entries(signals, dates_by_ticker):
        candidates = by_ticker[signal.ticker]
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


# --- Bilesenlerin tahmin gucu --------------------------------------------------

POWER_COMPONENTS: tuple[str, ...] = ("composite", "llm", "fundamental", "analyst", "momentum")
MIN_CROSS_SECTION = 20


@dataclass(frozen=True)
class ComponentObservation:
    ticker: str
    as_of_date: date
    scores: dict[str, float]  # "composite" + mevcut bilesenler


@dataclass(frozen=True)
class ComponentPower:
    component: str
    horizon: int
    days: int
    observations: int
    mean_ic: float | None
    positive_ic_pct: float | None
    spread_pct: float | None


def _ranks(values: list[float]) -> list[float]:
    """Esit degerlere ortalama sira veren 1 tabanli siralar."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mean_x, mean_y = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def compute_component_power(
    observations: list[ComponentObservation],
    prices: list[PricePoint],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    components: tuple[str, ...] = POWER_COMPONENTS,
    min_cross_section: int = MIN_CROSS_SECTION,
) -> list[ComponentPower]:
    """Her giris gununde hisseler bilesen skoruna gore siralanir; sonraki N islem
    gunundeki getiriyle sira korelasyonu (IC) ve en ust/en alt beslik getiri farki
    hesaplanir. Ayni gun tum hisseler ayni piyasayi yasadigi icin endeks
    duzeltmesi gerekmez. Vadeler ortustugu icin gunler bagimsiz degildir."""
    by_ticker: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for price in prices:
        if price.close and price.close > 0:
            by_ticker[price.ticker].append((price.price_date, float(price.close)))
    for rows in by_ticker.values():
        rows.sort(key=lambda row: row[0])
    dates_by_ticker = {ticker: [day for day, _ in rows] for ticker, rows in by_ticker.items()}

    # (vade, bilesen, giris gunu) -> [(skor, ileri getiri)]
    sections: dict[tuple[int, str, date], list[tuple[float, float]]] = defaultdict(list)
    for observation, base_index in _entries(observations, dates_by_ticker):
        candidates = by_ticker[observation.ticker]
        base_date, base_close = candidates[base_index]
        for horizon in horizons:
            if base_index + horizon >= len(candidates):
                continue
            forward = (candidates[base_index + horizon][1] / base_close - 1) * 100
            for component in components:
                score = observation.scores.get(component)
                if score is not None:
                    sections[(horizon, component, base_date)].append((float(score), forward))

    results: list[ComponentPower] = []
    for horizon in horizons:
        for component in components:
            ics: list[float] = []
            spreads: list[float] = []
            count = 0
            for (h, c, _), pairs in sections.items():
                if h != horizon or c != component or len(pairs) < min_cross_section:
                    continue
                ic = spearman([score for score, _ in pairs], [ret for _, ret in pairs])
                if ic is None:
                    continue
                ics.append(ic)
                count += len(pairs)
                ranked = sorted(pairs)
                bucket = max(1, len(ranked) // 5)
                top = [ret for _, ret in ranked[-bucket:]]
                bottom = [ret for _, ret in ranked[:bucket]]
                spreads.append(sum(top) / len(top) - sum(bottom) / len(bottom))
            results.append(
                ComponentPower(
                    component=component,
                    horizon=horizon,
                    days=len(ics),
                    observations=count,
                    mean_ic=round(sum(ics) / len(ics), 4) if ics else None,
                    positive_ic_pct=(
                        round(sum(ic > 0 for ic in ics) / len(ics) * 100, 1) if ics else None
                    ),
                    spread_pct=round(sum(spreads) / len(spreads), 2) if spreads else None,
                )
            )
    return results
