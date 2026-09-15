import type { Price } from "./types";
import { normalizePrices, movingAverage, wilderRsi, bollingerBands } from "./chart-data";

export interface TvCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface TvLinePoint {
  time: string;
  value: number;
}

export interface TvVolumePoint {
  time: string;
  value: number;
  color: string;
}

export interface ChartDataBundle {
  candles: TvCandle[];
  area: TvLinePoint[];
  volume: TvVolumePoint[];
  ma20: TvLinePoint[];
  ma50: TvLinePoint[];
  ma200: TvLinePoint[];
  bbUpper: TvLinePoint[];
  bbLower: TvLinePoint[];
  avgPrice: TvLinePoint[];
  rsi: TvLinePoint[];
  minDate: string;
  maxDate: string;
  count: number;
}

/**
 * Prepares sorted and sanitized data bundles suitable for TradingView lightweight-charts.
 */
export function prepareTradingViewData(rawPrices: Price[]): ChartDataBundle {
  const normalized = normalizePrices(rawPrices);
  if (!normalized.length) {
    return {
      candles: [],
      area: [],
      volume: [],
      ma20: [],
      ma50: [],
      ma200: [],
      bbUpper: [],
      bbLower: [],
      avgPrice: [],
      rsi: [],
      minDate: "",
      maxDate: "",
      count: 0,
    };
  }

  const closes = normalized.map((p) => p.close);
  const ma20Series = movingAverage(closes, 20);
  const ma50Series = movingAverage(closes, 50);
  const ma200Series = movingAverage(closes, 200);
  const bbSeries = bollingerBands(closes, 20, 2);
  const rsiSeries = wilderRsi(closes, 14);

  const candles: TvCandle[] = [];
  const area: TvLinePoint[] = [];
  const volume: TvVolumePoint[] = [];
  const ma20: TvLinePoint[] = [];
  const ma50: TvLinePoint[] = [];
  const ma200: TvLinePoint[] = [];
  const bbUpper: TvLinePoint[] = [];
  const bbLower: TvLinePoint[] = [];
  const avgPrice: TvLinePoint[] = [];
  const rsi: TvLinePoint[] = [];

  for (let i = 0; i < normalized.length; i++) {
    const row = normalized[i];
    const prevClose = i > 0 ? normalized[i - 1].close : (row.avg_price ?? row.close);
    const open = prevClose;
    const close = row.close;
    const high = Math.max(row.high ?? close, open, close);
    const low = Math.min(row.low ?? close, open, close);
    const isUp = close >= open;

    candles.push({
      time: row.date,
      open,
      high,
      low,
      close,
    });

    area.push({
      time: row.date,
      value: close,
    });

    if (row.volume_try != null && row.volume_try >= 0) {
      volume.push({
        time: row.date,
        value: row.volume_try,
        color: isUp ? "rgba(22, 163, 74, 0.55)" : "rgba(239, 68, 68, 0.55)",
      });
    }

    const m20 = ma20Series[i];
    if (m20 != null && Number.isFinite(m20)) {
      ma20.push({ time: row.date, value: m20 });
    }

    const m50 = ma50Series[i];
    if (m50 != null && Number.isFinite(m50)) {
      ma50.push({ time: row.date, value: m50 });
    }

    const m200 = ma200Series[i];
    if (m200 != null && Number.isFinite(m200)) {
      ma200.push({ time: row.date, value: m200 });
    }

    const bbu = bbSeries.upper[i];
    if (bbu != null && Number.isFinite(bbu)) {
      bbUpper.push({ time: row.date, value: bbu });
    }

    const bbl = bbSeries.lower[i];
    if (bbl != null && Number.isFinite(bbl)) {
      bbLower.push({ time: row.date, value: bbl });
    }

    if (row.avg_price != null && Number.isFinite(row.avg_price)) {
      avgPrice.push({ time: row.date, value: row.avg_price });
    }

    const r = rsiSeries[i];
    if (r != null && Number.isFinite(r)) {
      rsi.push({ time: row.date, value: r });
    }
  }

  return {
    candles,
    area,
    volume,
    ma20,
    ma50,
    ma200,
    bbUpper,
    bbLower,
    avgPrice,
    rsi,
    minDate: normalized[0].date,
    maxDate: normalized[normalized.length - 1].date,
    count: normalized.length,
  };
}

/**
 * Returns TradingView chart layout and styling options for dark or light theme.
 */
export function getTradingViewThemeColors(isDark: boolean) {
  if (isDark) {
    return {
      background: "#0c111d",
      textColor: "#94a3b8",
      gridColor: "#1e293b",
      borderColor: "#334155",
      crosshairColor: "#64748b",
      upColor: "#22c55e",
      downColor: "#ef4444",
      areaTopColor: "rgba(59, 130, 246, 0.28)",
      areaBottomColor: "rgba(59, 130, 246, 0.02)",
      lineColor: "#3b82f6",
      ma20Color: "#10b981",
      ma50Color: "#f59e0b",
      ma200Color: "#ec4899",
      bbColor: "#38bdf8",
      avgPriceColor: "#8b5cf6",
      rsiColor: "#06b6d4",
    };
  }
  return {
    background: "#ffffff",
    textColor: "#475569",
    gridColor: "#f1f5f9",
    borderColor: "#e2e8f0",
    crosshairColor: "#94a3b8",
    upColor: "#16a34a",
    downColor: "#dc2626",
    areaTopColor: "rgba(37, 99, 235, 0.22)",
    areaBottomColor: "rgba(37, 99, 235, 0.01)",
    lineColor: "#2563eb",
    ma20Color: "#059669",
    ma50Color: "#d97706",
    ma200Color: "#db2777",
    bbColor: "#0284c7",
    avgPriceColor: "#7c3aed",
    rsiColor: "#0891b2",
  };
}
