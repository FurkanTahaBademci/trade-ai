import type { SignalHorizonStat } from "@/lib/types";
import { formatNumber, formatPercent, signalName } from "@/lib/format";
import { EmptyState } from "@/components/ui";

const LABELS: SignalHorizonStat["label"][] = ["VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"];

export function SignalAccuracyTable({ stats }: { stats: SignalHorizonStat[] }) {
  const horizons = [...new Set(stats.map((item) => item.horizon))].sort((a, b) => a - b);
  const find = (horizon: number, label: string) => stats.find((item) => item.horizon === horizon && item.label === label);
  const hasData = stats.some((item) => item.observation_count > 0);

  if (!hasData) return <div className="panel-flat"><EmptyState compact title="Henüz yeterli veri yok" description="Sinyaller ve onları izleyen fiyat günleri biriktikçe bu tablo otomatik dolacak."/></div>;

  return <div className="table-shell overflow-x-auto"><table className="data-table min-w-[560px]">
    <thead><tr><th>Etiket</th>{horizons.map((horizon) => <th key={horizon}>{horizon} işlem günü sonra</th>)}</tr></thead>
    <tbody>{LABELS.map((label) => <tr key={label}><td className="font-medium">{signalName(label)}</td>{horizons.map((horizon) => {
      const cell = find(horizon, label);
      if (!cell || cell.observation_count === 0) return <td key={horizon} className="text-[var(--text-muted)]">—</td>;
      return <td key={horizon}>
        <span className={(cell.average_return_pct ?? 0) >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{formatPercent(cell.average_return_pct, true)}</span>
        {cell.hit_rate_pct != null && <span className="ml-2 text-[10px] text-[var(--text-muted)]">isabet %{formatNumber(cell.hit_rate_pct, 0)}</span>}
        <span className="ml-2 text-[10px] text-[var(--text-muted)]">n={cell.observation_count}</span>
      </td>;
    })}</tr>)}</tbody>
  </table></div>;
}
