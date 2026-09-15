"use client";

import dynamic from "next/dynamic";
import type { Price } from "@/lib/types";

const DynamicTvChart = dynamic(
  () => import("./tradingview-chart").then((m) => m.TradingViewChart),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-[420px] place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] text-sm text-[var(--text-muted)] animate-pulse">
        Gelişmiş grafik yükleniyor...
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
  return (
    <div className="space-y-4">
      <DynamicTvChart prices={prices} error={error} ticker={ticker} />
    </div>
  );
}

