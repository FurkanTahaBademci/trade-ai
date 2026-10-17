"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import type { MarketHeatmapData, MarketHeatmapStock } from "@/lib/types";
import { formatMoney, formatPercent, signalName } from "@/lib/format";
import { matchesTurkishSearch, rankTurkishSearchMatch } from "@/lib/turkish";
import { Icon } from "./icon";

export function MarketHeatmap({ data }: { data: MarketHeatmapData | null }) {
  const [metric, setMetric] = useState<"change" | "score">("change");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  // Mobilde 60+ sektör alt alta binlerce piksel tutuyordu: dar ekranda sektörler
  // varsayılan olarak tek satırlık özet halinde gelir, dokununca açılır. Kullanıcı
  // seçimi yoksa (undefined) görünürlüğü CSS kırılımı belirler.
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const isDesktop = useMediaQuery("(min-width: 768px)");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 150);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const sectors = data?.sectors || [];
  const summary = data?.summary;

  const filteredSectors = useMemo(() => {
    const q = debouncedQuery.trim();
    return sectors
      .filter((sec) => !selectedSector || sec.name === selectedSector)
      .map((sec) => {
        const matchingStocks = sec.stocks
          .filter((s) => !q || matchesTurkishSearch(q, s.ticker, s.name))
          .sort((a, b) => {
            if (!q) return 0;
            const rankA = rankTurkishSearchMatch(q, a.ticker, a.name);
            const rankB = rankTurkishSearchMatch(q, b.ticker, b.name);
            return rankA - rankB || a.ticker.localeCompare(b.ticker, "tr-TR");
          });
        return {
          ...sec,
          stocks: matchingStocks,
        };
      })
      .filter((sec) => sec.stocks.length > 0);
  }, [sectors, selectedSector, debouncedQuery]);

  const forceOpen = Boolean(selectedSector || debouncedQuery.trim());
  const isOpen = (name: string) => forceOpen || (expanded[name] ?? isDesktop);
  const toggleSector = (name: string) => setExpanded((current) => ({ ...current, [name]: !(current[name] ?? window.matchMedia("(min-width: 768px)").matches) }));
  const setAll = (open: boolean) => setExpanded(Object.fromEntries(sectors.map((sector) => [sector.name, open])));
  const tilesClass = (name: string) => forceOpen || expanded[name] === true ? "grid" : expanded[name] === false ? "hidden" : "hidden md:grid";

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
      if (s == null) return "bg-[var(--surface-raised)] border-[var(--border)] text-[var(--text-muted)]";
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
    <div className="space-y-4">
      {/* 1. Kontrol ve Özet Çubuğu */}
      <div className="flex flex-col gap-4 rounded border border-[var(--border)] bg-[var(--surface)] p-4 sm:flex-row sm:items-center sm:justify-between">
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

          <div className="flex rounded border border-[var(--border)] bg-[var(--surface-raised)] p-0.5 text-xs">
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

      {!forceOpen && filteredSectors.length > 1 && (
        <div className="flex items-center justify-between text-xs text-[var(--text-muted)] md:hidden">
          <span>Hisseleri görmek için sektöre dokunun.</span>
          <span className="flex shrink-0 gap-1.5">
            <button type="button" className="pill" onClick={() => setAll(true)}>Tümünü aç</button>
            <button type="button" className="pill" onClick={() => setAll(false)}>Kapat</button>
          </span>
        </div>
      )}

      {/* 3. Sektörel Isı Haritası Izgarası (Treemap / Grid) */}
      <div className="grid gap-2 md:grid-cols-2 md:gap-5 xl:grid-cols-3">
        {filteredSectors.map((sector) => (
          <div
            key={sector.name}
            className="flex flex-col rounded border border-[var(--border)] bg-[var(--surface)] p-3 shadow-xs transition hover:border-[var(--border-strong)] md:p-4"
          >
            {/* Sektör Başlığı: mobilde aç/kapa düğmesi */}
            <button
              type="button"
              onClick={() => toggleSector(sector.name)}
              aria-expanded={isOpen(sector.name)}
              aria-controls={`sektor-${slug(sector.name)}`}
              disabled={forceOpen}
              className={`flex w-full items-center justify-between gap-3 text-left ${isOpen(sector.name) ? "mb-3 border-b border-[var(--border-subtle)] pb-2.5" : ""}`}
            >
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold tracking-[-0.01em] text-[var(--text)]">
                  {sector.name}
                </h3>
                <p className="text-xs text-[var(--text-muted)]">
                  {sector.stocks.length} hisse · {formatMoney(sector.total_market_cap_try, true)}
                </p>
              </div>
              <span className="flex shrink-0 items-center gap-2">
                <span
                  className={`pill text-xs font-semibold ${
                    sector.avg_change_pct >= 0 ? "pill-positive" : "pill-negative"
                  }`}
                >
                  {formatPercent(sector.avg_change_pct, true)}
                </span>
                {!forceOpen && <Icon name="chevron" size={16} className={`text-[var(--text-muted)] transition-transform ${isOpen(sector.name) ? "rotate-90" : ""}`} />}
              </span>
            </button>

            {/* Sektör içi hisse kutucukları */}
            <div id={`sektor-${slug(sector.name)}`} className={`${tilesClass(sector.name)} flex-1 grid-cols-3 gap-2 sm:grid-cols-4`}>
              {sector.stocks.slice(0, 16).map((stock) => (
                <Link prefetch={false}
                  key={stock.ticker}
                  href={`/piyasalar/${stock.ticker}`}
                  className={`group relative flex flex-col justify-between rounded border p-2 text-center transition hover:scale-[1.03] hover:z-10 ${getStockBg(
                    stock
                  )}`}
                  title={`${stock.name} (${stock.ticker})\nSon Fiyat: ${formatMoney(
                    stock.last_price
                  )}\nGünlük Değişim: ${formatPercent(
                    stock.change_pct,
                    true
                  )}\nSinyal: ${stock.composite_score == null ? "skor yok" : `${Math.round(stock.composite_score)} (${signalName(stock.signal_label ?? "")})`}`}
                >
                  <span className="truncate text-xs font-bold leading-tight tracking-tight">
                    {stock.ticker}
                  </span>
                  <div className="mt-1 flex flex-col text-[11px] font-medium leading-none">
                    {metric === "change" ? (
                      <>
                        <span className="opacity-90">{formatPercent(stock.change_pct, true)}</span>
                        <span className="mt-1 text-[10px] opacity-75">
                          {formatMoney(stock.last_price)}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="font-bold">{stock.composite_score == null ? "—" : Math.round(stock.composite_score)}</span>
                        <span className="mt-1 text-[10px] opacity-75 truncate">
                          {stock.signal_label ? signalName(stock.signal_label) : "Skor yok"}
                        </span>
                      </>
                    )}
                  </div>
                </Link>
              ))}
            </div>

            {sector.stocks.length > 16 && isOpen(sector.name) && (
              <p className="mt-2.5 text-center text-xs text-[var(--text-muted)]">
                + {sector.stocks.length - 16} hisse daha
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function slug(value: string) {
  return value.toLocaleLowerCase("tr-TR").replace(/[^a-z0-9ğüşıöç]+/g, "-");
}

/** Sunucuda ve ilk hidrasyonda masaüstü varsayılır; yalnız aria-expanded için kullanılır. */
function useMediaQuery(query: string) {
  return useSyncExternalStore(
    (onChange) => {
      const media = window.matchMedia(query);
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => true,
  );
}
