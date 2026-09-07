import type { Price } from "@/lib/types";
import { formatMoney } from "@/lib/format";

export function PriceChart({ prices }: { prices: Price[] }) {
  if (prices.length < 2) return <div className="grid h-64 place-items-center text-xs text-[var(--text-muted)]">Grafik için yeterli fiyat verisi yok.</div>;
  const width = 800, height = 250, pad = 18; const values = prices.map((item) => item.close); const min = Math.min(...values), max = Math.max(...values); const range = max - min || 1;
  const points = values.map((value, index) => `${pad + index * ((width - pad * 2) / (values.length - 1))},${height - pad - ((value - min) / range) * (height - pad * 2)}`).join(" ");
  const area = `${pad},${height - pad} ${points} ${width - pad},${height - pad}`;
  return <div><div className="mb-3 flex justify-between text-[11px] text-[var(--text-muted)]"><span>{prices[0].date}</span><span>En yüksek {formatMoney(max)}</span><span>{prices.at(-1)?.date}</span></div><svg className="h-auto w-full" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="90 günlük kapanış fiyat grafiği"><defs><linearGradient id="priceArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".24"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((p) => <line key={p} x1={pad} x2={width-pad} y1={height*p} y2={height*p} stroke="var(--chart-grid)" strokeDasharray="4 5"/>)}<polygon points={area} fill="url(#priceArea)"/><polyline points={points} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></div>;
}
