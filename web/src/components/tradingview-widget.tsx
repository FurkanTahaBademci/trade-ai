"use client";

import { useEffect, useRef, useState } from "react";

export function TradingViewWidget({ ticker }: { ticker: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [loadError, setLoadError] = useState(false);

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

    const symbol = `BIST:${ticker.trim().toUpperCase()}`;
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
  }, [ticker, theme]);

  if (loadError) {
    return (
      <div className="grid h-[520px] place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 text-center text-sm text-[var(--text-muted)]">
        TradingView servisine bağlanırken bir sorun oluştu. Lütfen bağlantınızı kontrol edin veya TradeAI Fiyat Grafiği sekmesini kullanın.
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]" style={{ height: 560 }}>
      <div ref={containerRef} className="tradingview-widget-container h-full w-full" />
    </div>
  );
}
