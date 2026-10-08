import type { IndexPrice, PaperSnapshot } from "@/lib/types";
import { PerformanceChart } from "./performance-chart";

export function EquityChart({ snapshots, indexPrices }: { snapshots: PaperSnapshot[]; indexPrices?: IndexPrice[] }) {
  return <PerformanceChart source={snapshots.map((row) => ({ date: row.snapshot_date, value: row.total_equity }))} label="Paper portföy değer grafiği" benchmark={indexPrices}/>;
}
