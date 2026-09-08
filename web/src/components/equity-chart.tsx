import type { PaperSnapshot } from "@/lib/types";
import { PerformanceChart } from "./performance-chart";

export function EquityChart({ snapshots }: { snapshots: PaperSnapshot[] }) {
  return <PerformanceChart source={snapshots.map((row) => ({ date: row.snapshot_date, value: row.total_equity }))} label="Paper portföy değer grafiği"/>;
}
