import type { ComponentPower } from "@/lib/types";
import { componentName, formatNumber, formatPercent } from "@/lib/format";
import { EmptyState } from "@/components/ui";

const COMPONENTS = ["composite", "llm", "fundamental", "analyst", "momentum"];

function label(component: string) {
  return component === "composite" ? "Bileşik skor" : componentName(component);
}

// IC: günlük sıra korelasyonu. ±0,02 altı gürültü sayılır; 0,05 üstü güçlü kabul edilir.
function tone(ic: number | null) {
  if (ic == null || Math.abs(ic) < 0.02) return "text-[var(--text-muted)]";
  return ic > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
}

export function ComponentPowerTable({ rows }: { rows: ComponentPower[] }) {
  const horizons = [...new Set(rows.map((item) => item.horizon))].sort((a, b) => a - b);
  const find = (component: string, horizon: number) => rows.find((item) => item.component === component && item.horizon === horizon);
  if (!rows.some((item) => item.days > 0)) return <div className="panel-flat"><EmptyState compact title="Henüz yeterli veri yok" description="Her gün en az 20 hissede skor ve ardından gelen fiyat günleri biriktikçe bu tablo dolacak."/></div>;

  return <div className="table-shell overflow-x-auto"><table className="data-table min-w-[560px]">
    <caption className="sr-only">Bileşenlerin sonraki getiriyi sıralama gücü</caption>
    <thead><tr><th scope="col">Bileşen</th>{horizons.map((horizon) => <th key={horizon} scope="col">{horizon} işlem günü</th>)}</tr></thead>
    <tbody>{COMPONENTS.map((component) => <tr key={component}><td className={component === "composite" ? "font-semibold" : "font-medium"}>{label(component)}</td>{horizons.map((horizon) => {
      const cell = find(component, horizon);
      if (!cell || cell.mean_ic == null) return <td key={horizon} className="text-[var(--text-muted)]">—</td>;
      return <td key={horizon}>
        <span className={`terminal-mono font-semibold ${tone(cell.mean_ic)}`}>{cell.mean_ic > 0 ? "+" : ""}{formatNumber(cell.mean_ic, 3)}</span>
        <span className="ml-2 text-[10px] text-[var(--text-muted)]">pozitif gün %{formatNumber(cell.positive_ic_pct, 0)}</span>
        <div className="text-[10px] text-[var(--text-muted)]">üst−alt beşlik {formatPercent(cell.spread_pct, true)} · {cell.days} gün</div>
      </td>;
    })}</tr>)}</tbody>
  </table></div>;
}
