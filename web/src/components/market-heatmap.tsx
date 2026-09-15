"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { MarketHeatmapData, MarketHeatmapStock } from "@/lib/types";
import { formatMoney, formatPercent } from "@/lib/format";
import { Icon } from "./icon";

export function MarketHeatmap({ data }: { data: MarketHeatmapData | null }) {
  const [metric, setMetric] = useState<"change" | "score">("change");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const sectors = data?.sectors || [];
  const summary = data?.summary;

  const filteredSectors = useMemo(() => {
    const q = searchQuery.trim().toUpperCase();
    return sectors
      .filter((sec) => !selectedSector || sec.name === selectedSector)
      .map((sec) => {
        const matchingStocks = sec.stocks.filter(
          (s) => !q || s.ticker.includes(q) || s.name.toUpperCase().includes(q)
        );
        return {
          ...sec,
          stocks: matchingStocks,
        };
      })
      .filter((sec) => sec.stocks.length > 0);
  }, [sectors, selectedSector, searchQuery]);

  if (!data || !sectors.length) {
    return (
      <div className="panel-flat p-8 text-center text-sm text-[var(--text-muted)]">
        <Icon name="activity" size={24} className="mx-auto mb-2 opacity-50" />
        Isı haritası için yeterli fiyat verisi bekleniyor.
      </div>
    );
  }

  function getStockBg(stock: MarketHeatmapStock) {
    if (metric === "score") {
      const s = stock.composite_score;
      if (s >= 75) return "bg-[var(--positive-soft)] border-[color-mix(in_srgb,var(--positive)_40%,transparent)] text-[var(--positive)]";
      if (s >= 60) return "bg-[color-mix(in_srgb,var(--positive)_15%,transparent)] border-[color-mix(in_srgb,var(--positive)_25%,transparent)] text-[var(--positive)]";
      if (s <= 35) return "bg-[var(--negative-soft)] border-[color-mix(in_srgb,var(--negative)_40%,transparent)] text-[var(--negative)]";
      if (s <= 45) return "bg-[color-mix(in_srgb,var(--negative)_15%,transparent)] border-[color-mix(in_srgb,var(--negative)_25%,transparent)] text-[var(--negative)]";
      return "bg-[var(--surface-raised)] border-[var(--border)] text-[var(--text-secondary)]";
    }

    const c = stock.change_pct;
    if (c >= 3.0) return "bg-[var(--positive)] text-[var(--primary-contrast)] border-transparent shadow-sm";
    if (c >= 1.0) return "bg-[var(--positive-soft)] border-[color-mix(in_srgb,var(--positive)_30%,transparent)] text-[var(--positive)]";
    if (c > 0.0) return "bg-[color-mix(in_srgb,var(--positive)_12%,transparent)] border-[color-mix(in_srgb,var(--positive)_20%,transparent)] text-[var(--positive)]";
    if (c <= -3.0) return "bg-[var(--negative)] text-[var(--primary-contrast)] border-transparent shadow-sm";
    if (c <= -1.0) return "bg-[var(--negative-soft)] border-[color-mix(in_srgb,var(--negative)_30%,transparent)] text-[var(--negative)]";
    if (c < 0.0) return "bg-[color-mix(in_srgb,var(--negative)_12%,transparent)] border-[color-mix(in_srgb,var(--negative)_20%,transparent)] text-[var(--negative)]";
    return "bg-[var(--surface-raised)] border-[var(--border)] text-[var(--text-muted)]";
  }

  return (
    <div className="space-y-6">
      {/* 1. Kontrol ve Özet Çubuğu */}
      <div className="flex flex-col gap-4 rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Özet sayaçlar */}
        {summary && (
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="font-semibold text-[var(--text)]">
              {summary.total_instruments} BIST Hissesi
            </span>
            <span className="flex items-center gap-1 font-medium text-[var(--positive)]">
              <span className="h-2 w-2 rounded-full bg-[var(--positive)]" />
              {summary.positive_count} Yükselen
            </span>
            <span className="flex items-center gap-1 font-medium text-[var(--negative)]">
              <span className="h-2 w-2 rounded-full bg-[var(--negative)]" />
              {summary.negative_count} Düşen
            </span>
            <span className="text-[var(--text-muted)]">
              Ort. Getiri:{" "}
              <span
                className={`font-semibold ${
                  summary.market_avg_change_pct >= 0
                    ? "text-[var(--positive)]"
                    : "text-[var(--negative)]"
                }`}
              >
                {formatPercent(summary.market_avg_change_pct, true)}
              </span>
            </span>
          </div>
        )}

        {/* Metrik Seçici ve Arama */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Icon
              name="search"
              size={14}
              className="absolute left-2.5 top-2.5 text-[var(--text-muted)]"
            />
            <input
              type="text"
              placeholder="Hisse veya sektör ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input h-8 pl-8 text-xs sm:w-48"
            />
          </div>

          <div className="flex rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setMetric("change")}
              className={`rounded-[8px] px-2.5 py-1 font-medium transition ${
                metric === "change"
                  ? "bg-[var(--surface)] font-semibold text-[var(--text)] shadow-xs"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
            >
              Getiri (%)
            </button>
            <button
              type="button"
              onClick={() => setMetric("score")}
              className={`rounded-[8px] px-2.5 py-1 font-medium transition ${
                metric === "score"
                  ? "bg-[var(--surface)] font-semibold text-[var(--text)] shadow-xs"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
            >
              Sinyal Skoru
            </button>
          </div>
        </div>
      </div>

      {/* 2. Sektör Filtre Hapları */}
      <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
        <button
          type="button"
          onClick={() => setSelectedSector(null)}
          className={`shrink-0 rounded-[8px] px-3 py-1.5 font-medium transition ${
            selectedSector === null
              ? "bg-[var(--primary)] text-[var(--primary-contrast)] font-semibold"
              : "bg-[var(--surface-raised)] text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
          }`}
        >
          Tüm Sektörler ({sectors.length})
        </button>
        {sectors.map((sec) => (
          <button
            key={sec.name}
            type="button"
            onClick={() => setSelectedSector(selectedSector === sec.name ? null : sec.name)}
            className={`shrink-0 rounded-[8px] px-3 py-1.5 font-medium transition ${
              selectedSector === sec.name
                ? "bg-[var(--primary)] text-[var(--primary-contrast)] font-semibold"
                : "bg-[var(--surface-raised)] text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
            }`}
          >
            {sec.name} ({sec.stock_count})
          </button>
        ))}
      </div>

      {/* 3. Sektörel Isı Haritası Izgarası (Treemap / Grid) */}
      <div className="grid gap-5 sm:grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        {filteredSectors.map((sector) => (
          <div
            key={sector.name}
            className="flex flex-col rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs transition hover:border-[var(--border-strong)]"
          >
            {/* Sektör Başlığı */}
            <div className="mb-3 flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
              <div>
                <h3 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text)]">
                  {sector.name}
                </h3>
                <p className="text-[10px] text-[var(--text-muted)]">
                  {sector.stocks.length} hisse · {formatMoney(sector.total_market_cap_try, true)}
                </p>
              </div>
              <span
                className={`pill text-[11px] font-semibold ${
                  sector.avg_change_pct >= 0 ? "pill-positive" : "pill-negative"
                }`}
              >
                {formatPercent(sector.avg_change_pct, true)}
              </span>
            </div>

            {/* Sektör içi hisse kutucukları */}
            <div className="grid flex-1 grid-cols-3 gap-2 sm:grid-cols-4">
              {sector.stocks.slice(0, 16).map((stock) => (
                <Link
                  key={stock.ticker}
                  href={`/piyasalar/${stock.ticker}`}
                  className={`group relative flex flex-col justify-between rounded-[10px] border p-2 text-center transition hover:scale-[1.03] hover:z-10 ${getStockBg(
                    stock
                  )}`}
                  title={`${stock.name} (${stock.ticker})\nSon Fiyat: ${formatMoney(
                    stock.last_price
                  )}\nGünlük Değişim: ${formatPercent(
                    stock.change_pct,
                    true
                  )}\nSinyal: ${stock.composite_score} (${stock.signal_label})`}
                >
                  <span className="truncate text-xs font-bold leading-tight tracking-tight">
                    {stock.ticker}
                  </span>
                  <div className="mt-1 flex flex-col text-[10px] font-medium leading-none">
                    {metric === "change" ? (
                      <>
                        <span className="opacity-90">{formatPercent(stock.change_pct, true)}</span>
                        <span className="mt-1 text-[8px] opacity-75">
                          {formatMoney(stock.last_price)}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="font-bold">{Math.round(stock.composite_score)}</span>
                        <span className="mt-1 text-[8px] opacity-75 truncate">
                          {stock.signal_label}
                        </span>
                      </>
                    )}
                  </div>
                </Link>
              ))}
            </div>

            {sector.stocks.length > 16 && (
              <p className="mt-2.5 text-center text-[10px] text-[var(--text-muted)]">
                + {sector.stocks.length - 16} hisse daha
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
