import type { BacktestPoint, IndexPrice } from "@/lib/types";
import { PerformanceChart } from "./performance-chart";

export function BacktestEquityChart({ points, indexPrices }: { points: BacktestPoint[]; indexPrices?: IndexPrice[] }) {
  return <PerformanceChart source={points.map((row) => ({ date: row.point_date, value: row.total_equity }))} label="Backtest sermaye eğrisi" benchmark={indexPrices}/>;
}
