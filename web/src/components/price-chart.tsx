"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { expandPrices, type CompactPrice } from "@/lib/price-series";

const loadChart = () => import("./tradingview-chart").then((m) => m.TradingViewChart);
// Grafik parçası (lightweight-charts) bileşen ilk kez çizilmeyi beklemeden, modül
// tarayıcıda yüklenir yüklenmez indirilmeye başlar.
if (typeof window !== "undefined") void loadChart().catch(() => undefined);

// Yüklenirken son düzenin iskeleti: kontrol satırı + grafik alanı; yerleşim kaymaz.
function ChartSkeleton() {
  return (
    <div className="min-w-0" aria-busy="true" role="status">
      <span className="sr-only">Grafik yükleniyor</span>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2" aria-hidden="true">
        <div className="flex flex-wrap gap-1">
          {Array.from({ length: 7 }, (_, index) => <span key={index} className="h-9 w-10 animate-pulse rounded border border-[var(--border)] bg-[var(--surface-raised)]" />)}
        </div>
        <div className="flex gap-1">
          <span className="h-9 w-[140px] animate-pulse rounded border border-[var(--border)] bg-[var(--surface-raised)]" />
          <span className="h-9 w-10 animate-pulse rounded border border-[var(--border)] bg-[var(--surface-raised)] sm:w-28" />
        </div>
      </div>
      <div className="mb-3 hidden h-9 animate-pulse rounded bg-[var(--surface-raised)] sm:block" aria-hidden="true" />
      <div className="relative h-[380px] overflow-hidden rounded border border-[var(--border)] bg-[var(--surface)]" aria-hidden="true">
        <svg className="absolute inset-0 h-full w-full animate-pulse text-[var(--border)]" viewBox="0 0 400 100" preserveAspectRatio="none">
          <polyline fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" points="0,70 30,64 60,68 90,52 120,58 150,44 180,50 210,36 240,42 270,30 300,38 330,26 360,32 400,20" />
        </svg>
        <div className="absolute inset-x-0 bottom-0 flex h-16 items-end gap-1 px-2 pb-2">
          {Array.from({ length: 28 }, (_, index) => <span key={index} className="flex-1 animate-pulse rounded-sm bg-[var(--surface-raised)]" style={{ height: `${25 + ((index * 37) % 70)}%` }} />)}
        </div>
      </div>
    </div>
  );
}

const DynamicTvChart = dynamic(loadChart, { ssr: false, loading: ChartSkeleton });

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
