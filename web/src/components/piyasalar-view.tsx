"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { InstrumentSummary, MarketHeatmapData, MarketHeatmapStock } from "@/lib/types";
import { DEFAULT_MARKETS_VIEW, marketsViewQuery, nextSort, parseMarketsView, type MarketsSortKey, type MarketsViewMode, type MarketsViewState } from "@/lib/markets-view";
import { InstrumentList } from "./instrument-list";
import { MarketHeatmap } from "./market-heatmap";
import { Icon } from "./icon";

export function PiyasalarView({
  instruments,
  heatmap,
  initialView = DEFAULT_MARKETS_VIEW,
}: {
  instruments: InstrumentSummary[];
  heatmap: MarketHeatmapData | null;
  initialView?: MarketsViewState;
}) {
  const [state, setState] = useState<MarketsViewState>(initialView);
  const quotes = useMemo(() => {
    const map: Record<string, MarketHeatmapStock> = {};
    for (const sector of heatmap?.sectors ?? []) for (const stock of sector.stocks) map[stock.ticker] = stock;
    return map;
  }, [heatmap]);

  // Geri/ileri tuşu: görünüm değişimi geçmişe yazıldığı için adresten yeniden oku.
  useEffect(() => {
    const onPop = () => setState(parseMarketsView(Object.fromEntries(new URLSearchParams(window.location.search))));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Görünüm değişimi geçmişe eklenir (geri tuşu önceki görünümü açar); sıralama
  // yalnız mevcut adresi günceller. Next native History API'yi router'la eşler.
  const commit = useCallback((next: MarketsViewState, mode: "push" | "replace") => {
    setState(next);
    const query = marketsViewQuery(next);
    const url = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    if (mode === "push") window.history.pushState(null, "", url);
    else window.history.replaceState(null, "", url);
  }, []);

  const setView = (view: MarketsViewMode) => { if (view !== state.view) commit({ ...state, view }, "push"); };
  const onSort = (column: MarketsSortKey) => commit({ ...state, ...nextSort(state, column) }, "replace");
  const onSortChange = (sort: MarketsSortKey, order: MarketsViewState["order"]) => commit({ ...state, sort, order }, "replace");
  const view = state.view;

  return (
    <div className="space-y-4">
      {/* Görünüm Değiştirici Tab'ler */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
        <div className="flex items-center gap-1.5 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-1 text-xs">
          <button
            type="button"
            onClick={() => setView("heatmap")}
            aria-pressed={view === "heatmap"}
            className={`flex items-center gap-1.5 rounded px-3.5 py-1.5 font-medium transition ${
              view === "heatmap"
                ? "bg-[var(--surface)] text-[var(--text)] font-semibold shadow-xs"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            <Icon name="spark" size={14} />
            Isı haritası
          </button>
          <button
            type="button"
            onClick={() => setView("table")}
            aria-pressed={view === "table"}
            className={`flex items-center gap-1.5 rounded px-3.5 py-1.5 font-medium transition ${
              view === "table"
                ? "bg-[var(--surface)] text-[var(--text)] font-semibold shadow-xs"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            <Icon name="activity" size={14} />
            Hisse listesi
          </button>
        </div>

        <span className="hidden text-xs text-[var(--text-muted)] sm:inline">
          {view === "heatmap"
            ? "BIST sektör performans ve getiri haritası"
            : `${instruments.length} kayıtlı hisse senedi`}
        </span>
      </div>

      {/* Seçili Görünüm */}
      {view === "heatmap" ? (
        <MarketHeatmap data={heatmap} />
      ) : (
        <InstrumentList instruments={instruments} quotes={quotes} sort={state.sort} order={state.order} onSort={onSort} onSortChange={onSortChange} />
      )}
    </div>
  );
}
