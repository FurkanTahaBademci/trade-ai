import type { Fundamental } from "./types";

export type Valuation = { pe: number | null; pb: number | null; basis: string | null };

const basisLabels: Record<string, string> = { annual: "yıllık kâr", ttm: "son 12 ay kârı", annualized: "yıllıklandırılmış dönem kârı" };

function multiple(marketCap: number | null | undefined, denominator: number | null | undefined) {
  if (marketCap == null || denominator == null || !(marketCap > 0) || !(denominator > 0)) return null;
  return marketCap / denominator;
}

// F/K, API'nin hesapladığı son 12 ay kârıyla bulunur; dönem kârı yıl içi
// kümülatif olduğundan doğrudan bölmek ara dönemlerde çarpanı şişirir.
export function valuationMultiples(marketCap: number | null | undefined, fundamental: Fundamental | undefined): Valuation {
  if (!fundamental) return { pe: null, pb: null, basis: null };
  return {
    pe: multiple(marketCap, fundamental.ttm_net_income),
    pb: multiple(marketCap, fundamental.equity),
    basis: fundamental.ttm_basis ? basisLabels[fundamental.ttm_basis] ?? null : null,
  };
}
