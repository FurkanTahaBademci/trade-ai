"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { Price } from "@/lib/types";
import { TradingViewWidget } from "./tradingview-widget";

const DynamicTvChart = dynamic(
  () => import("./tradingview-chart").then((m) => m.TradingViewChart),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-[420px] place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] text-sm text-[var(--text-muted)] animate-pulse">
        TradingView grafiği yükleniyor...
      </div>
    ),
  }
);

interface PriceChartProps {
  prices: Price[];
  error?: boolean;
  ticker?: string;
}

export function PriceChart({ prices, error = false, ticker = "THYAO" }: PriceChartProps) {
  const [activeTab, setActiveTab] = useState<"native" | "advanced">("native");

  return (
    <div className="space-y-4">
      {/* Tab Switcher: TradeAI Native TradingView vs TradingView Advanced Widget */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
        <div className="flex rounded-lg border border-[var(--border)] p-1 bg-[var(--surface-raised)]">
          <button
            type="button"
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "native"
                ? "bg-[var(--primary)] text-white shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            onClick={() => setActiveTab("native")}
          >
            <span>📈</span> TradeAI Grafiği (Hızlı)
          </button>
          <button
            type="button"
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "advanced"
                ? "bg-[var(--primary)] text-white shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            onClick={() => setActiveTab("advanced")}
          >
            <span>🌐</span> TradingView Gelişmiş Platformu
          </button>
        </div>

        <div className="text-xs text-[var(--text-muted)]">
          {activeTab === "native" ? (
            <span>İş Yatırım EOD veri tabanı · Lightweight Charts v5</span>
          ) : (
            <span>Resmi TradingView BIST:{ticker.toUpperCase()} terminali</span>
          )}
        </div>
      </div>

      {/* Active Tab View */}
      {activeTab === "native" ? (
        <DynamicTvChart prices={prices} error={error} ticker={ticker} />
      ) : (
        <TradingViewWidget ticker={ticker} />
      )}
    </div>
  );
}
