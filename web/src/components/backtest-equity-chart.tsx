import type { BacktestPoint } from "@/lib/types";
import { PerformanceChart } from "./performance-chart";

export function BacktestEquityChart({ points }: { points: BacktestPoint[] }) {
  return <PerformanceChart source={points.map((row) => ({ date: row.point_date, value: row.total_equity }))} label="Backtest sermaye eğrisi"/>;
}
