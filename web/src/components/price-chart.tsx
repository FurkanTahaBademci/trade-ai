"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { expandPrices, type CompactPrice } from "@/lib/price-series";

const DynamicTvChart = dynamic(
  () => import("./tradingview-chart").then((m) => m.TradingViewChart),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-[420px] place-items-center rounded border border-[var(--border)] bg-[var(--surface-raised)] text-sm text-[var(--text-muted)] animate-pulse">
        Gelişmiş grafik yükleniyor...
      </div>
    ),
  }
);

interface PriceChartProps {
  series: CompactPrice[];
  error?: boolean;
  ticker?: string;
}

export function PriceChart({ series, error = false, ticker = "THYAO" }: PriceChartProps) {
  const prices = useMemo(() => expandPrices(series), [series]);
  return (
    <div className="space-y-4">
      <DynamicTvChart prices={prices} error={error} ticker={ticker} />
    </div>
  );
}
