"use client";

import { useState } from "react";
import type { Instrument, MarketHeatmapData } from "@/lib/types";
import { InstrumentList } from "./instrument-list";
import { MarketHeatmap } from "./market-heatmap";
import { Icon } from "./icon";

export function PiyasalarView({
  instruments,
  heatmap,
}: {
  instruments: Instrument[];
  heatmap: MarketHeatmapData | null;
}) {
  const [view, setView] = useState<"heatmap" | "table">("heatmap");

  return (
    <div className="space-y-6">
      {/* Görünüm Değiştirici Tab'ler */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
        <div className="flex items-center gap-1.5 rounded-[12px] border border-[var(--border)] bg-[var(--surface-raised)] p-1 text-xs">
          <button
            type="button"
            onClick={() => setView("heatmap")}
            className={`flex items-center gap-1.5 rounded-[9px] px-3.5 py-1.5 font-medium transition ${
              view === "heatmap"
                ? "bg-[var(--surface)] text-[var(--text)] font-semibold shadow-xs"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            <Icon name="spark" size={14} />
            Sektörel Isı Haritası
          </button>
          <button
            type="button"
            onClick={() => setView("table")}
            className={`flex items-center gap-1.5 rounded-[9px] px-3.5 py-1.5 font-medium transition ${
              view === "table"
                ? "bg-[var(--surface)] text-[var(--text)] font-semibold shadow-xs"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            <Icon name="activity" size={14} />
            Hisse Listesi & Arama
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
        <InstrumentList instruments={instruments} />
      )}
    </div>
  );
}
