// Hisse tarayıcı: URL parametreleri <-> API sorgusu. Sayfa sunucuda render edilir;
// filtreler GET formuyla URL'ye yazılır, böylece her tarama paylaşılabilir.

import type { ScreenerRow } from "@/lib/types";

export const SCREENER_SORTS = ["ticker", "composite_score", "change_1d_pct", "change_1m_pct", "change_3m_pct", "market_cap_try", "volume_try", "pe_ratio", "pb_ratio", "roe_pct", "revenue_yoy_pct", "net_income_yoy_pct", "upside_pct"] as const;
export type ScreenerSort = (typeof SCREENER_SORTS)[number];

export const NUMERIC_FILTERS = ["min_score", "max_pe", "max_pb", "min_roe", "min_revenue_growth", "min_upside", "min_change_1m", "min_market_cap"] as const;
type NumericFilter = (typeof NUMERIC_FILTERS)[number];

/** Kullanıcıya gösterilen sinyal grupları ve API etiketleri. */
export const SIGNAL_GROUPS: Record<string, { label: string; labels: string[] }> = {
  guclu: { label: "Çok pozitif", labels: ["VERY_POSITIVE"] },
  pozitif: { label: "Pozitif ve üstü", labels: ["VERY_POSITIVE", "POSITIVE"] },
  notr: { label: "Nötr", labels: ["NEUTRAL"] },
  negatif: { label: "Negatif ve altı", labels: ["NEGATIVE", "VERY_NEGATIVE"] },
};

export const MARKET_CAP_OPTIONS = [
  { value: "1000000000", label: "≥ 1 Mr ₺" },
  { value: "10000000000", label: "≥ 10 Mr ₺" },
  { value: "50000000000", label: "≥ 50 Mr ₺" },
  { value: "100000000000", label: "≥ 100 Mr ₺" },
];

export type ScreenerParams = {
  q?: string;
  sector?: string;
  signal?: string;
  sort: ScreenerSort;
  order: "asc" | "desc";
  /** Gösterilen satır sayısı; varsayılan sayfa boyutu URL'ye yazılmaz. */
  limit?: string;
} & Partial<Record<NumericFilter, string>>;

export const SCREENER_PAGE_SIZE = 100;
export const SCREENER_MAX_ROWS = 1000;

export function screenerLimit(params: Pick<ScreenerParams, "limit">) {
  const value = Number(params.limit);
  if (!Number.isInteger(value) || value <= SCREENER_PAGE_SIZE) return SCREENER_PAGE_SIZE;
  return Math.min(SCREENER_MAX_ROWS, Math.ceil(value / SCREENER_PAGE_SIZE) * SCREENER_PAGE_SIZE);
}

export const SCREENER_PRESETS: { label: string; description: string; params: Partial<ScreenerParams> }[] = [
  { label: "Ucuz ve güçlü skor", description: "F/K ≤ 10, skor ≥ 60", params: { max_pe: "10", min_score: "60", sort: "pe_ratio", order: "asc" } },
  { label: "Analist favorileri", description: "Potansiyel ≥ %30, pozitif sinyal", params: { min_upside: "30", signal: "pozitif", sort: "upside_pct", order: "desc" } },
  { label: "Momentum liderleri", description: "1 ayda ≥ %10", params: { min_change_1m: "10", sort: "change_1m_pct", order: "desc" } },
  { label: "Kârlı büyüme", description: "ROE ≥ %25, gelir büyümesi ≥ %30", params: { min_roe: "25", min_revenue_growth: "30", sort: "roe_pct", order: "desc" } },
  { label: "Büyük şirketler", description: "Piyasa değeri ≥ 50 Mr ₺", params: { min_market_cap: "50000000000", sort: "market_cap_try", order: "desc" } },
];

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined) {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** "10,5" gibi Türkçe ondalıkları da kabul eder; geçersiz değer filtreyi yok sayar. */
export function parseDecimal(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseScreenerParams(raw: RawParams): ScreenerParams {
  const sort = first(raw.sort) as ScreenerSort;
  const params: ScreenerParams = {
    sort: SCREENER_SORTS.includes(sort) ? sort : "composite_score",
    order: first(raw.order) === "asc" ? "asc" : "desc",
  };
  const q = first(raw.q).slice(0, 64); if (q) params.q = q;
  const sector = first(raw.sector).slice(0, 64); if (sector) params.sector = sector;
  const signal = first(raw.signal); if (signal in SIGNAL_GROUPS) params.signal = signal;
  const limit = screenerLimit({ limit: first(raw.limit) }); if (limit !== SCREENER_PAGE_SIZE) params.limit = String(limit);
  for (const name of NUMERIC_FILTERS) {
    const value = first(raw[name]);
    if (parseDecimal(value) != null) params[name] = value;
  }
  return params;
}

/** Backend `/api/markets/screener` sorgusu. */
export function screenerApiQuery(params: ScreenerParams, limit = screenerLimit(params)) {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.sector) query.set("sector", params.sector);
  for (const label of params.signal ? SIGNAL_GROUPS[params.signal].labels : []) query.append("label", label);
  for (const name of NUMERIC_FILTERS) {
    const value = parseDecimal(params[name]);
    if (value != null) query.set(name, String(value));
  }
  query.set("sort", params.sort);
  query.set("order", params.order);
  query.set("limit", String(limit));
  return query.toString();
}

/** Sayfa URL'si; varsayılan sıralama URL'ye yazılmaz. */
export function screenerHref(params: Partial<ScreenerParams>, base = "/tarayici") {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === "") continue;
    if (key === "sort" && value === "composite_score") continue;
    if (key === "order" && value === "desc") continue;
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `${base}?${text}` : base;
}

/** Sütun başlığına tıklanınca: aynı sütunda yön değişir, yeni sütunda büyükten küçüğe başlar (F/K ve PD/DD küçükten). */
export function sortHref(params: ScreenerParams, column: ScreenerSort) {
  const ascendingFirst = column === "pe_ratio" || column === "pb_ratio" || column === "ticker";
  const order = params.sort === column ? (params.order === "desc" ? "asc" : "desc") : ascendingFirst ? "asc" : "desc";
  return screenerHref({ ...params, sort: column, order, limit: undefined });
}

/** Sonraki 100 satırı da gösteren adres; sınıra gelindiyse null. */
export function moreHref(params: ScreenerParams, matched: number) {
  const limit = screenerLimit(params);
  if (matched <= limit || limit >= SCREENER_MAX_ROWS) return null;
  return screenerHref({ ...params, limit: String(limit + SCREENER_PAGE_SIZE) });
}

export function activeFilterCount(params: ScreenerParams) {
  // Sıralama ve satır sayısı filtre sayılmaz.
  return [params.q, params.sector, params.signal, ...NUMERIC_FILTERS.map((name) => params[name])].filter(Boolean).length;
}

/** Tarayıcı tablosunun kolonları (sıralanabilir). */
export const TABLE_COLUMNS: { key: ScreenerSort; label: string; title?: string }[] = [
  { key: "ticker", label: "Hisse" },
  { key: "change_1d_pct", label: "Gün" },
  { key: "change_1m_pct", label: "1 ay" },
  { key: "market_cap_try", label: "Piy. değeri" },
  { key: "composite_score", label: "Skor" },
  { key: "pe_ratio", label: "F/K", title: "Son 12 ay net kârıyla" },
  { key: "pb_ratio", label: "PD/DD" },
  { key: "roe_pct", label: "ROE" },
  { key: "revenue_yoy_pct", label: "Gelir büy.", title: "Son dönem, yıllık" },
  { key: "upside_pct", label: "Analist pot.", title: "Konsensüs hedef fiyata göre" },
];

/** Tabloya (istemci bileşenine) giden satır: yalnız gösterilen alanlar. */
export type TableRow = Pick<ScreenerRow, "ticker" | "name" | "sector" | "last_price" | "change_1d_pct" | "change_1m_pct" | "market_cap_try" | "composite_score" | "signal_label" | "pe_ratio" | "pb_ratio" | "roe_pct" | "revenue_yoy_pct" | "upside_pct" | "analyst_count">;

export function toTableRow(row: ScreenerRow): TableRow {
  const { ticker, name, sector, last_price, change_1d_pct, change_1m_pct, market_cap_try, composite_score, signal_label, pe_ratio, pb_ratio, roe_pct, revenue_yoy_pct, upside_pct, analyst_count } = row;
  return { ticker, name, sector, last_price, change_1d_pct, change_1m_pct, market_cap_try, composite_score, signal_label, pe_ratio, pb_ratio, roe_pct, revenue_yoy_pct, upside_pct, analyst_count };
}
