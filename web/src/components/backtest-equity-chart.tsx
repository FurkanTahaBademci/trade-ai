import { formatMoney } from "@/lib/format";
import type { BacktestPoint } from "@/lib/types";

export function BacktestEquityChart({ points: source }: { points: BacktestPoint[] }) {
  const points = [...source].sort((a, b) => a.point_date.localeCompare(b.point_date));
  if (points.length < 2) return <div className="grid h-56 place-items-center px-5 text-center text-xs text-[var(--text-muted)]">Sermaye eğrisi için en az iki fiyat günü gerekiyor.</div>;
  const width = 900, height = 250, pad = 20;
  const values = points.map((point) => point.total_equity);
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const line = values.map((value, index) => `${pad + index * ((width - pad * 2) / (values.length - 1))},${height - pad - ((value - min) / range) * (height - pad * 2)}`).join(" ");
  const area = `${pad},${height-pad} ${line} ${width-pad},${height-pad}`;
  return <div><div className="mb-3 flex justify-between text-[11px] text-[var(--text-muted)]"><span>{points[0].point_date}</span><span>Tepe {formatMoney(max)}</span><span>{points.at(-1)?.point_date}</span></div><svg className="h-auto w-full" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Backtest sermaye eğrisi"><defs><linearGradient id="backtestArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".22"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((value) => <line key={value} x1={pad} x2={width-pad} y1={height*value} y2={height*value} stroke="var(--chart-grid)" strokeDasharray="4 5"/>)}<polygon points={area} fill="url(#backtestArea)"/><polyline points={line} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></div>;
}
