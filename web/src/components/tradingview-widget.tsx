"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icon";

export function TradingViewWidget({
  ticker,
  onSwitchToNative,
}: {
  ticker: string;
  onSwitchToNative?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [loadError, setLoadError] = useState(false);
  const symbol = `BIST:${ticker.trim().toUpperCase()}`;

  useEffect(() => {
    const checkTheme = () => {
      const isLight = document.documentElement.getAttribute("data-theme") === "light";
      setTheme(isLight ? "light" : "dark");
    };

    checkTheme();

    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    const handleCustomTheme = () => checkTheme();
    window.addEventListener("trade-ai:theme-change", handleCustomTheme);

    return () => {
      observer.disconnect();
      window.removeEventListener("trade-ai:theme-change", handleCustomTheme);
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = "";
    setLoadError(false);

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.width = "100%";
    widgetDiv.style.height = "100%";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.onerror = () => setLoadError(true);

    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval: "D",
      timezone: "Europe/Istanbul",
      theme: theme === "light" ? "light" : "dark",
      style: "1",
      locale: "tr",
      enable_publishing: false,
      allow_symbol_change: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: true,
      calendar: false,
      hide_volume: false,
      support_host: "https://www.tradingview.com",
    });

    container.appendChild(widgetDiv);
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [symbol, theme]);

  return (
    <div className="space-y-4">
      {/* Informative Guidance Banner */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="pill pill-primary font-semibold">BIST Lisans Bilgilendirmesi</span>
              <span className="text-xs text-[var(--text-muted)]">{symbol}</span>
            </div>
            <p className="text-xs leading-5 text-[var(--text-secondary)]">
              Borsa İstanbul (BIST) veri lisans sözleşmeleri gereğince, üçüncü taraf web sitelerine gömülü (embedded) widget&apos;larda BIST sembollerinin gösterimi kısıtlanmaktadır (<em>&quot;Bu sembol sadece TradingView&apos;da mevcuttur&quot;</em> uyarısı bu nedenle çıkmaktadır).
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              TradeAI bünyesindeki <strong>&quot;TradeAI Grafiği&quot;</strong> sekmesi, İş Yatırım resmi veri tabanımız üzerinden TradingView Lightweight Charts canvas motoruyla <strong>kesintisiz</strong> çalışmaktadır.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
            {onSwitchToNative && (
              <button
                type="button"
                onClick={onSwitchToNative}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3.5 py-2 text-xs font-medium text-[var(--text)] transition hover:bg-[var(--surface-hover)]"
              >
                ← TradeAI Grafiğine Dön
              </button>
            )}

            <a
              href={`https://tr.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:opacity-90"
            >
              <span>↗</span> TradingView.com&apos;da Aç
            </a>
          </div>
        </div>
      </div>

      {/* Embedded Widget */}
      {loadError ? (
        <div className="grid h-[520px] place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 text-center text-sm text-[var(--text-muted)]">
          TradingView servisine bağlanırken bir sorun oluştu.
        </div>
      ) : (
        <div
          className="relative w-full overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]"
          style={{ height: 560 }}
        >
          <div ref={containerRef} className="tradingview-widget-container h-full w-full" />
        </div>
      )}
    </div>
  );
}
