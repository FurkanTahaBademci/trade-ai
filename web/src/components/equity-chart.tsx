import type { PaperSnapshot } from "@/lib/types";
import { formatMoney } from "@/lib/format";

export function EquityChart({ snapshots }: { snapshots: PaperSnapshot[] }) {
  const rows = [...snapshots].reverse();
  if (rows.length < 2) return <div className="grid h-52 place-items-center text-xs text-[var(--text-muted)]">Performans eğrisi için ikinci işlem günü bekleniyor.</div>;
  const width = 800, height = 220, pad = 18; const values = rows.map((row) => row.total_equity); const min = Math.min(...values), max = Math.max(...values); const range = max - min || 1;
  const points = values.map((value, index) => `${pad + index * ((width - pad * 2) / (values.length - 1))},${height - pad - ((value - min) / range) * (height - pad * 2)}`).join(" ");
  const area = `${pad},${height-pad} ${points} ${width-pad},${height-pad}`;
  return <div><div className="mb-2 flex justify-between text-[11px] text-[var(--text-muted)]"><span>{rows[0].snapshot_date}</span><span>{formatMoney(max)}</span><span>{rows.at(-1)?.snapshot_date}</span></div><svg className="h-auto w-full" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Paper portföy değer grafiği"><defs><linearGradient id="equityArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".2"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((value) => <line key={value} x1={pad} x2={width-pad} y1={height*value} y2={height*value} stroke="var(--chart-grid)" strokeDasharray="4 5"/>)}<polygon points={area} fill="url(#equityArea)"/><polyline points={points} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></div>;
}
