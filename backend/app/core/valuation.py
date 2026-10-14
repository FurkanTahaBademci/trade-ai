"""Degerleme carpanlari (F/K, PD/DD) icin saf yardimcilar.

BIST finansal tablolari yil ici kumulatiftir: 6. donem net kari ocak-haziran
toplamidir. Piyasa degerini bu kara bolmek F/K'yi 6. donemde ~2, 3. donemde ~4
kat sisirir. Bu yuzden F/K son 12 ay (TTM) kariyla hesaplanir:

    TTM = bu yil donem kari + onceki yil yillik kar - onceki yil ayni donem kari

Onceki yil verisi yoksa donem kari yilliklandirilir (x 12 / donem).
"""

from collections.abc import Mapping

TtmBasis = str  # "annual" | "ttm" | "annualized"


def trailing_net_income(
    *,
    year: int,
    period: int,
    net_income: float | None,
    history: Mapping[tuple[int, int], float | None],
) -> tuple[float | None, TtmBasis | None]:
    """Son 12 ay net kari ve hesap yontemi. `history` (yil, donem) -> kumulatif kar."""
    if net_income is None or period <= 0:
        return None, None
    if period == 12:
        return net_income, "annual"
    prior_annual = history.get((year - 1, 12))
    prior_same = history.get((year - 1, period))
    if prior_annual is not None and prior_same is not None:
        return net_income + prior_annual - prior_same, "ttm"
    return net_income * 12 / period, "annualized"


def price_multiple(market_cap: float | None, denominator: float | None) -> float | None:
    """Piyasa degeri / (kar veya ozsermaye). Zarar veya negatif ozsermayede anlamsizdir."""
    if not market_cap or not denominator or market_cap <= 0 or denominator <= 0:
        return None
    return market_cap / denominator
