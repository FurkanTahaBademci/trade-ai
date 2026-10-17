// /piyasalar görünüm durumu <-> URL. Görünüm (liste / ısı haritası) ve liste
// sıralaması adres çubuğunda tutulur; böylece bağlantı paylaşılabilir ve geri
// tuşu aynı ekranı açar. Varsayılan değerler URL'ye yazılmaz.

export type MarketsViewMode = "table" | "heatmap";
export type MarketsSortKey = "ticker" | "price" | "change" | "volume" | "score";
export type SortOrder = "asc" | "desc";
export type MarketsViewState = { view: MarketsViewMode; sort: MarketsSortKey; order: SortOrder };

export const MARKETS_SORT_KEYS: MarketsSortKey[] = ["ticker", "price", "change", "volume", "score"];
export const MARKETS_SORT_LABELS: Record<MarketsSortKey, string> = { ticker: "Kod", price: "Son fiyat", change: "Günlük değişim", volume: "İşlem hacmi", score: "Bileşik skor" };
export const DEFAULT_MARKETS_VIEW: MarketsViewState = { view: "table", sort: "ticker", order: "asc" };

/** Yeni bir sütuna geçildiğinde başlangıç yönü: kod A→Z, sayısal sütunlar büyükten küçüğe. */
export function defaultOrder(sort: MarketsSortKey): SortOrder {
  return sort === "ticker" ? "asc" : "desc";
}

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined) {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export function parseMarketsView(raw: RawParams): MarketsViewState {
  const view = first(raw.view) === "heatmap" ? "heatmap" : "table";
  const sortValue = first(raw.sort) as MarketsSortKey;
  const sort = MARKETS_SORT_KEYS.includes(sortValue) ? sortValue : DEFAULT_MARKETS_VIEW.sort;
  const orderValue = first(raw.order);
  const order = orderValue === "asc" || orderValue === "desc" ? orderValue : defaultOrder(sort);
  return { view, sort, order };
}

export function marketsViewQuery(state: MarketsViewState) {
  const query = new URLSearchParams();
  if (state.view !== DEFAULT_MARKETS_VIEW.view) query.set("view", state.view);
  if (state.sort !== DEFAULT_MARKETS_VIEW.sort) query.set("sort", state.sort);
  if (state.order !== defaultOrder(state.sort)) query.set("order", state.order);
  return query.toString();
}

/** Başlığa tıklama: aynı sütunda yön değişir, yeni sütun kendi varsayılan yönüyle başlar. */
export function nextSort(state: Pick<MarketsViewState, "sort" | "order">, column: MarketsSortKey): Pick<MarketsViewState, "sort" | "order"> {
  if (state.sort === column) return { sort: column, order: state.order === "asc" ? "desc" : "asc" };
  return { sort: column, order: defaultOrder(column) };
}
