"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  AreaSeries,
  BarSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import type { Price } from "@/lib/types";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { rangeStart } from "@/lib/chart-data";
import {
  getTradingViewThemeColors,
  prepareTradingViewData,
  type TvCandle,
} from "@/lib/tradingview-data";
import { chartButton } from "./chart-frame";

const ranges = [
  { label: "1H", days: 7 },
  { label: "1A", days: 30 },
  { label: "3A", days: 90 },
  { label: "6A", days: 180 },
  { label: "1Y", days: 365 },
  { label: "3Y", days: 1095 },
  { label: "Tümü", days: 0 },
];

export function TradingViewChart({
  prices,
  error = false,
  ticker,
}: {
  prices: Price[];
  error?: boolean;
  ticker?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Series references
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const barSeriesRef = useRef<ISeriesApi<"Bar"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpperSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const avgPriceSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const [isDark, setIsDark] = useState(true);
  const [chartMode, setChartMode] = useState<"candle" | "area" | "bar">("candle");
  const [showMa20, setShowMa20] = useState(true);
  const [showMa50, setShowMa50] = useState(false);
  const [showMa200, setShowMa200] = useState(false);
  const [showBb, setShowBb] = useState(false);
  const [showAvgPrice, setShowAvgPrice] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const [activeRange, setActiveRange] = useState<number | null>(90);
  const [customRange, setCustomRange] = useState({ start: "", end: "" });
  const [isFullscreen, setIsFullscreen] = useState(false);

  // HUD / Legend state
  const [hoveredData, setHoveredData] = useState<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number | null;
    changePct: number | null;
    ma20?: number | null;
    ma50?: number | null;
    ma200?: number | null;
    bbUpper?: number | null;
    bbLower?: number | null;
    avgPrice?: number | null;
    rsi?: number | null;
  } | null>(null);

  const dataBundle = useMemo(() => prepareTradingViewData(prices), [prices]);

  const priceMap = useMemo(() => {
    const map = new Map<
      string,
      TvCandle & {
        volume?: number;
        ma20?: number;
        ma50?: number;
        ma200?: number;
        bbUpper?: number;
        bbLower?: number;
        avgPrice?: number;
        rsi?: number;
      }
    >();
    const ma20Map = new Map(dataBundle.ma20.map((p) => [p.time, p.value]));
    const ma50Map = new Map(dataBundle.ma50.map((p) => [p.time, p.value]));
    const ma200Map = new Map(dataBundle.ma200.map((p) => [p.time, p.value]));
    const bbUpperMap = new Map(dataBundle.bbUpper.map((p) => [p.time, p.value]));
    const bbLowerMap = new Map(dataBundle.bbLower.map((p) => [p.time, p.value]));
    const avgMap = new Map(dataBundle.avgPrice.map((p) => [p.time, p.value]));
    const rsiMap = new Map(dataBundle.rsi.map((p) => [p.time, p.value]));
    const volMap = new Map(dataBundle.volume.map((p) => [p.time, p.value]));

    dataBundle.candles.forEach((c) => {
      map.set(c.time, {
        ...c,
        volume: volMap.get(c.time),
        ma20: ma20Map.get(c.time),
        ma50: ma50Map.get(c.time),
        ma200: ma200Map.get(c.time),
        bbUpper: bbUpperMap.get(c.time),
        bbLower: bbLowerMap.get(c.time),
        avgPrice: avgMap.get(c.time),
        rsi: rsiMap.get(c.time),
      });
    });
    return map;
  }, [dataBundle]);

  const latestCandle = dataBundle.candles.at(-1) ?? null;
  const prevCandle = dataBundle.candles.length > 1 ? dataBundle.candles.at(-2) : null;
  const defaultHud = useMemo(() => {
    if (!latestCandle) return null;
    const detailed = priceMap.get(latestCandle.time);
    const prevClose = prevCandle?.close ?? detailed?.open ?? latestCandle.close;
    const changePct = prevClose > 0 ? (latestCandle.close / prevClose - 1) * 100 : 0;
    return {
      date: latestCandle.time,
      open: latestCandle.open,
      high: latestCandle.high,
      low: latestCandle.low,
      close: latestCandle.close,
      volume: detailed?.volume ?? null,
      changePct,
      ma20: detailed?.ma20 ?? null,
      ma50: detailed?.ma50 ?? null,
      ma200: detailed?.ma200 ?? null,
      bbUpper: detailed?.bbUpper ?? null,
      bbLower: detailed?.bbLower ?? null,
      avgPrice: detailed?.avgPrice ?? null,
      rsi: detailed?.rsi ?? null,
    };
  }, [latestCandle, prevCandle, priceMap]);

  const displayHud = hoveredData ?? defaultHud;

  // Theme detection
  useEffect(() => {
    const updateTheme = () => {
      const themeAttr = document.documentElement.getAttribute("data-theme");
      setIsDark(themeAttr !== "light");
    };

    updateTheme();
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    const handleCustom = () => updateTheme();
    window.addEventListener("trade-ai:theme-change", handleCustom);

    return () => {
      observer.disconnect();
      window.removeEventListener("trade-ai:theme-change", handleCustom);
    };
  }, []);

  // Initialize TradingView Chart
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !dataBundle.candles.length) return;

    const themeColors = getTradingViewThemeColors(isDark);
    const chartHeight = showRsi ? 480 : 380;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: chartHeight,
      layout: {
        background: { type: ColorType.Solid, color: themeColors.background },
        textColor: themeColors.textColor,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: themeColors.gridColor },
        horzLines: { color: themeColors.gridColor },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: themeColors.crosshairColor,
          width: 1,
          style: LineStyle.Dashed,
        },
        horzLine: {
          color: themeColors.crosshairColor,
          width: 1,
          style: LineStyle.Dashed,
        },
      },
      rightPriceScale: {
        borderColor: themeColors.borderColor,
        scaleMargins: {
          top: 0.08,
          bottom: 0.22,
        },
      },
      timeScale: {
        borderColor: themeColors.borderColor,
        timeVisible: true,
        secondsVisible: false,
      },
      localization: {
        locale: "tr-TR",
        dateFormat: "yyyy-MM-dd",
      },
    });

    chartRef.current = chart;

    // 1. Candlestick Series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: themeColors.upColor,
      downColor: themeColors.downColor,
      borderUpColor: themeColors.upColor,
      borderDownColor: themeColors.downColor,
      wickUpColor: themeColors.upColor,
      wickDownColor: themeColors.downColor,
    });
    candleSeriesRef.current = candleSeries;

    // 2. Area Series
    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: themeColors.areaTopColor,
      bottomColor: themeColors.areaBottomColor,
      lineColor: themeColors.lineColor,
      lineWidth: 2,
    });
    areaSeriesRef.current = areaSeries;

    // 3. Bar Series
    const barSeries = chart.addSeries(BarSeries, {
      upColor: themeColors.upColor,
      downColor: themeColors.downColor,
    });
    barSeriesRef.current = barSeries;

    // 4. Volume Histogram (Overlay at bottom 20%)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // 5. Indicators
    const ma20Series = chart.addSeries(LineSeries, {
      color: themeColors.ma20Color,
      lineWidth: 2,
      priceLineVisible: false,
      title: "MA20",
    });
    ma20SeriesRef.current = ma20Series;

    const ma50Series = chart.addSeries(LineSeries, {
      color: themeColors.ma50Color,
      lineWidth: 2,
      priceLineVisible: false,
      title: "MA50",
    });
    ma50SeriesRef.current = ma50Series;

    const ma200Series = chart.addSeries(LineSeries, {
      color: themeColors.ma200Color,
      lineWidth: 2,
      priceLineVisible: false,
      title: "MA200",
    });
    ma200SeriesRef.current = ma200Series;

    const bbUpperSeries = chart.addSeries(LineSeries, {
      color: themeColors.bbColor,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      title: "BB Üst",
    });
    bbUpperSeriesRef.current = bbUpperSeries;

    const bbLowerSeries = chart.addSeries(LineSeries, {
      color: themeColors.bbColor,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      title: "BB Alt",
    });
    bbLowerSeriesRef.current = bbLowerSeries;

    const avgPriceSeries = chart.addSeries(LineSeries, {
      color: themeColors.avgPriceColor,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      title: "AOF",
    });
    avgPriceSeriesRef.current = avgPriceSeries;

    // 6. RSI Pane (Pane index 1)
    let rsiSeries: ISeriesApi<"Line"> | null = null;
    if (showRsi && dataBundle.rsi.length) {
      rsiSeries = chart.addSeries(
        LineSeries,
        {
          color: themeColors.rsiColor,
          lineWidth: 2,
          priceLineVisible: false,
          title: "RSI (14)",
        },
        1
      );
      rsiSeries.createPriceLine({
        price: 70,
        color: themeColors.gridColor,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "70",
      });
      rsiSeries.createPriceLine({
        price: 30,
        color: themeColors.gridColor,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "30",
      });
      rsiSeriesRef.current = rsiSeries;
    }

    // Set Data based on mode
    if (chartMode === "candle") {
      candleSeries.setData(dataBundle.candles as any);
      areaSeries.setData([]);
      barSeries.setData([]);
    } else if (chartMode === "area") {
      areaSeries.setData(dataBundle.area as any);
      candleSeries.setData([]);
      barSeries.setData([]);
    } else {
      barSeries.setData(dataBundle.candles as any);
      candleSeries.setData([]);
      areaSeries.setData([]);
    }

    volumeSeries.setData(dataBundle.volume as any);
    ma20Series.setData(showMa20 ? (dataBundle.ma20 as any) : []);
    ma50Series.setData(showMa50 ? (dataBundle.ma50 as any) : []);
    ma200Series.setData(showMa200 ? (dataBundle.ma200 as any) : []);
    bbUpperSeries.setData(showBb ? (dataBundle.bbUpper as any) : []);
    bbLowerSeries.setData(showBb ? (dataBundle.bbLower as any) : []);
    avgPriceSeries.setData(showAvgPrice ? (dataBundle.avgPrice as any) : []);
    if (rsiSeries && showRsi) {
      rsiSeries.setData(dataBundle.rsi as any);
    }

    // Set visible range preset
    if (activeRange === 0) {
      chart.timeScale().fitContent();
    } else if (activeRange && dataBundle.maxDate) {
      const fromDate = rangeStart(dataBundle.maxDate, activeRange);
      try {
        chart.timeScale().setVisibleRange({ from: fromDate as any, to: dataBundle.maxDate as any });
      } catch {
        chart.timeScale().fitContent();
      }
    } else if (customRange.start && customRange.end) {
      try {
        chart.timeScale().setVisibleRange({ from: customRange.start as any, to: customRange.end as any });
      } catch {
        chart.timeScale().fitContent();
      }
    } else {
      chart.timeScale().fitContent();
    }

    // Subscribe to Crosshair hover
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setHoveredData(null);
        return;
      }
      const timeStr = typeof param.time === "string" ? param.time : String(param.time);
      const row = priceMap.get(timeStr);
      if (!row) return;

      const prev = dataBundle.candles.findIndex((c) => c.time === timeStr);
      const prevC = prev > 0 ? dataBundle.candles[prev - 1].close : row.open;
      const changePct = prevC > 0 ? (row.close / prevC - 1) * 100 : 0;

      setHoveredData({
        date: row.time,
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close,
        volume: row.volume ?? null,
        changePct,
        ma20: row.ma20,
        ma50: row.ma50,
        ma200: row.ma200,
        bbUpper: row.bbUpper,
        bbLower: row.bbLower,
        avgPrice: row.avgPrice,
        rsi: row.rsi,
      });
    });

    // Resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.target === container) {
          chart.applyOptions({
            width: entry.contentRect.width,
          });
        }
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [
    dataBundle,
    isDark,
    chartMode,
    showMa20,
    showMa50,
    showMa200,
    showBb,
    showAvgPrice,
    showRsi,
    priceMap,
  ]);

  // Handle Range Preset Switch
  const handleRangePreset = (days: number) => {
    setActiveRange(days);
    setCustomRange({ start: "", end: "" });
    if (!chartRef.current || !dataBundle.maxDate) return;

    if (days === 0) {
      chartRef.current.timeScale().fitContent();
    } else {
      const fromDate = rangeStart(dataBundle.maxDate, days);
      try {
        chartRef.current.timeScale().setVisibleRange({
          from: fromDate as any,
          to: dataBundle.maxDate as any,
        });
      } catch {
        chartRef.current.timeScale().fitContent();
      }
    }
  };

  // Handle Custom Date Filter
  const handleCustomDate = (type: "start" | "end", val: string) => {
    const updated = { ...customRange, [type]: val };
    setCustomRange(updated);
    setActiveRange(null);
    if (updated.start && updated.end && updated.start <= updated.end && chartRef.current) {
      try {
        chartRef.current.timeScale().setVisibleRange({
          from: updated.start as any,
          to: updated.end as any,
        });
      } catch {
        // Fallback
      }
    }
  };

  // Zoom controls
  const handleZoom = (direction: "in" | "out") => {
    if (!chartRef.current) return;
    const timeScale = chartRef.current.timeScale();
    const logicalRange = timeScale.getVisibleLogicalRange();
    if (!logicalRange) return;

    const span = logicalRange.to - logicalRange.from;
    const factor = direction === "in" ? 0.7 : 1.4;
    const newSpan = Math.max(10, span * factor);
    const mid = (logicalRange.from + logicalRange.to) / 2;

    timeScale.setVisibleLogicalRange({
      from: mid - newSpan / 2,
      to: mid + newSpan / 2,
    });
  };

  if (error || !prices.length) {
    return (
      <div className="grid h-64 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 text-center text-sm text-[var(--text-muted)]">
        {error
          ? "Fiyat servisine ulaşılamadı. Sayfayı yenileyerek tekrar deneyin."
          : "Grafik için fiyat verisi bekleniyor."}
      </div>
    );
  }

  const containerClasses = isFullscreen
    ? "fixed inset-0 z-50 flex flex-col bg-[var(--background)] p-4 sm:p-6 overflow-y-auto"
    : "min-w-0";

  return (
    <div className={containerClasses} data-testid="price-chart">
      {/* Top Controls Bar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2.5">
        {/* Time Ranges */}
        <div className="flex flex-wrap gap-1" role="group" aria-label="Grafik dönemi">
          {ranges.map((r) => (
            <button
              key={r.label}
              type="button"
              className={`${chartButton} ${
                activeRange === r.days
                  ? "border-transparent bg-[var(--primary-soft)] !text-[var(--primary)] font-semibold"
                  : ""
              }`}
              onClick={() => handleRangePreset(r.days)}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Chart Style (Candle / Area / Bar) */}
        <div className="flex items-center gap-1">
          <div className="flex rounded-lg border border-[var(--border)] p-0.5 bg-[var(--surface-raised)]">
            <button
              type="button"
              className={`rounded px-2.5 py-1 text-xs transition ${
                chartMode === "candle"
                  ? "bg-[var(--primary)] text-white font-medium"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
              onClick={() => setChartMode("candle")}
              title="Mum Grafik (Candlestick)"
            >
              Mum
            </button>
            <button
              type="button"
              className={`rounded px-2.5 py-1 text-xs transition ${
                chartMode === "area"
                  ? "bg-[var(--primary)] text-white font-medium"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
              onClick={() => setChartMode("area")}
              title="Alan / Çizgi (Area)"
            >
              Çizgi
            </button>
            <button
              type="button"
              className={`rounded px-2.5 py-1 text-xs transition ${
                chartMode === "bar"
                  ? "bg-[var(--primary)] text-white font-medium"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
              onClick={() => setChartMode("bar")}
              title="Çubuk Grafik (OHLC Bar)"
            >
              Çubuk
            </button>
          </div>

          {/* Fullscreen Toggle Button */}
          <button
            type="button"
            className={`${chartButton} hidden sm:inline-flex items-center gap-1.5`}
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? "Tam ekrandan çık" : "Tam ekran"}
          >
            {isFullscreen ? "Küçült ✕" : "Tam Ekran ⛶"}
          </button>
        </div>
      </div>

      {/* Date & Zoom Secondary Row */}
      <div className="mb-3 grid grid-cols-2 items-end gap-2 sm:flex sm:flex-wrap">
        <label className="min-w-0 flex-1 text-xs text-[var(--text-muted)]">
          Başlangıç
          <input
            aria-label="Grafik başlangıcı"
            className="input mt-1 min-w-0"
            type="date"
            value={customRange.start || (activeRange ? rangeStart(dataBundle.maxDate, activeRange) : dataBundle.minDate)}
            onChange={(e) => handleCustomDate("start", e.target.value)}
          />
        </label>
        <label className="min-w-0 flex-1 text-xs text-[var(--text-muted)]">
          Bitiş
          <input
            aria-label="Grafik bitişi"
            className="input mt-1 min-w-0"
            type="date"
            value={customRange.end || dataBundle.maxDate}
            onChange={(e) => handleCustomDate("end", e.target.value)}
          />
        </label>
        <div className="col-span-2 flex gap-1">
          <button
            type="button"
            className={chartButton}
            aria-label="Yakınlaştır"
            onClick={() => handleZoom("in")}
            title="Yakınlaştır"
          >
            +
          </button>
          <button
            type="button"
            className={chartButton}
            aria-label="Uzaklaştır"
            onClick={() => handleZoom("out")}
            title="Uzaklaştır"
          >
            −
          </button>
          <button
            type="button"
            className={chartButton}
            aria-label="Tümünü sığdır"
            onClick={() => handleRangePreset(0)}
            title="Tümünü sığdır"
          >
            Sığdır
          </button>
        </div>
      </div>

      {/* Technical Indicators Row */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs">
        <button
          type="button"
          className={`${chartButton} ${
            showMa20
              ? "border-transparent bg-[var(--primary-soft)] !text-[var(--positive)] font-medium"
              : ""
          }`}
          onClick={() => setShowMa20(!showMa20)}
        >
          ● MA20
        </button>
        <button
          type="button"
          className={`${chartButton} ${
            showMa50
              ? "border-transparent bg-[var(--primary-soft)] !text-[var(--warning)] font-medium"
              : ""
          }`}
          onClick={() => setShowMa50(!showMa50)}
        >
          ● MA50
        </button>
        <button
          type="button"
          className={`${chartButton} ${
            showMa200
              ? "border-transparent bg-[var(--primary-soft)] !text-[#ec4899] font-medium"
              : ""
          }`}
          onClick={() => setShowMa200(!showMa200)}
        >
          ● MA200
        </button>
        <button
          type="button"
          className={`${chartButton} ${
            showBb
              ? "border-transparent bg-[var(--primary-soft)] !text-[#38bdf8] font-medium"
              : ""
          }`}
          onClick={() => setShowBb(!showBb)}
        >
          ● BB (20,2)
        </button>
        <button
          type="button"
          className={`${chartButton} ${
            showAvgPrice
              ? "border-transparent bg-[var(--primary-soft)] !text-[var(--accent,#8b5cf6)] font-medium"
              : ""
          }`}
          onClick={() => setShowAvgPrice(!showAvgPrice)}
        >
          ┄ AOF
        </button>
        <button
          type="button"
          className={`${chartButton} ${
            showRsi
              ? "border-transparent bg-[var(--primary-soft)] !text-[var(--primary)] font-medium"
              : ""
          }`}
          onClick={() => setShowRsi(!showRsi)}
        >
          ● RSI (14)
        </button>
      </div>

      {/* TradingView-style HUD / Legend Panel */}
      {displayHud && (
        <div
          className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-xs"
          data-testid="price-selection"
        >
          <div className="font-semibold text-[var(--text)]">
            {formatDate(displayHud.date)}
          </div>
          <div className="flex items-center gap-3 text-[var(--text-muted)]">
            <span>
              A: <strong className="font-medium text-[var(--text)]">{formatMoney(displayHud.open)}</strong>
            </span>
            <span>
              Y: <strong className="font-medium text-[var(--text)]">{formatMoney(displayHud.high)}</strong>
            </span>
            <span>
              D: <strong className="font-medium text-[var(--text)]">{formatMoney(displayHud.low)}</strong>
            </span>
            <span>
              K: <strong className="font-medium text-[var(--text)]">{formatMoney(displayHud.close)}</strong>
            </span>
          </div>

          {displayHud.changePct != null && (
            <span
              className={`font-semibold ${
                displayHud.changePct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"
              }`}
            >
              {formatPercent(displayHud.changePct, true)}
            </span>
          )}

          {displayHud.volume != null && displayHud.volume > 0 && (
            <span className="text-[var(--text-muted)]">
              Hacim: <strong className="font-medium text-[var(--text)]">{formatMoney(displayHud.volume, true)}</strong>
            </span>
          )}

          {showMa20 && displayHud.ma20 != null && (
            <span className="text-[var(--positive)]">
              MA20: <strong>{formatMoney(displayHud.ma20)}</strong>
            </span>
          )}
          {showMa50 && displayHud.ma50 != null && (
            <span className="text-[var(--warning)]">
              MA50: <strong>{formatMoney(displayHud.ma50)}</strong>
            </span>
          )}
          {showMa200 && displayHud.ma200 != null && (
            <span className="text-[#ec4899]">
              MA200: <strong>{formatMoney(displayHud.ma200)}</strong>
            </span>
          )}
          {showBb && displayHud.bbLower != null && displayHud.bbUpper != null && (
            <span className="text-[#38bdf8]">
              BB: <strong>{formatMoney(displayHud.bbLower)} - {formatMoney(displayHud.bbUpper)}</strong>
            </span>
          )}
          {showAvgPrice && displayHud.avgPrice != null && (
            <span className="text-[var(--accent,#8b5cf6)]">
              AOF: <strong>{formatMoney(displayHud.avgPrice)}</strong>
            </span>
          )}
          {showRsi && displayHud.rsi != null && (
            <span className="text-[var(--primary)]">
              RSI: <strong>{formatNumber(displayHud.rsi, 2)}</strong>
            </span>
          )}
        </div>
      )}

      {/* Chart Canvas Container */}
      <div
        ref={containerRef}
        className="relative w-full rounded-xl overflow-hidden border border-[var(--border)] bg-[var(--surface)] transition-all"
        style={{ minHeight: showRsi ? 480 : 380 }}
      />

      {/* Footer Info */}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--text-muted)]">
        <p>
          {dataBundle.count} işlem günü · Fare tekerleğiyle yakınlaştırabilir, basılı tutarak kaydırabilirsiniz.
        </p>
        <p>TradingView Lightweight Charts v5 ile güçlendirilmiştir.</p>
      </div>
    </div>
  );
}
