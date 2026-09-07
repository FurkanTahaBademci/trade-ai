"use client";

import { useMemo, useState } from "react";
import type { PointerEvent, ReactNode } from "react";
import { formatMoney, formatNumber, formatPercent } from "@/lib/format";
import type { Price } from "@/lib/types";

const WIDTH = 900, PRICE_HEIGHT = 265, VOLUME_TOP = 292, VOLUME_HEIGHT = 70;
const RSI_TOP = 390, RSI_HEIGHT = 70, PAD_X = 36;
const ranges = [{ label: "1A", days: 30 }, { label: "3A", days: 90 }, { label: "6A", days: 180 }, { label: "1Y", days: 365 }, { label: "3Y", days: 1095 }, { label: "Tümü", days: 0 }];

function movingAverage(rows: Price[], period: number) {
  return rows.map((_, index) => index < period - 1 ? null : rows.slice(index - period + 1, index + 1).reduce((sum, row) => sum + row.close, 0) / period);
}

function rsi(rows: Price[], period = 14) {
  const output: Array<number | null> = Array(rows.length).fill(null);
  for (let index = period; index < rows.length; index++) {
    let gains = 0, losses = 0;
    for (let cursor = index - period + 1; cursor <= index; cursor++) {
      const change = rows[cursor].close - rows[cursor - 1].close;
      if (change >= 0) gains += change; else losses -= change;
    }
    output[index] = losses === 0 ? 100 : 100 - (100 / (1 + gains / losses));
  }
  return output;
}

function linePoints(values: Array<number | null>, x: (index: number) => number, y: (value: number) => number) {
  return values.map((value, index) => value == null ? null : `${x(index)},${y(value)}`).filter(Boolean).join(" ");
}

export function PriceChart({ prices }: { prices: Price[] }) {
  const [rangeDays, setRangeDays] = useState(90);
  const [showMa20, setShowMa20] = useState(true);
  const [showMa50, setShowMa50] = useState(false);
  const [showAverage, setShowAverage] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const [hovered, setHovered] = useState<number | null>(null);
  const rows = useMemo(() => {
    if (!prices.length || rangeDays === 0) return prices;
    const end = new Date(`${prices.at(-1)?.date}T00:00:00`).getTime();
    const start = end - rangeDays * 86_400_000;
    return prices.filter((row) => new Date(`${row.date}T00:00:00`).getTime() >= start);
  }, [prices, rangeDays]);

  if (prices.length < 2 || rows.length < 2) return <div className="grid h-64 place-items-center text-xs text-[var(--text-muted)]">Grafik için yeterli fiyat verisi yok.</div>;

  const ma20 = movingAverage(rows, 20), ma50 = movingAverage(rows, 50), rsiValues = rsi(rows);
  const visibleValues = rows.flatMap((row) => [row.close, row.low, row.high, showAverage ? row.avg_price : null]).filter((value): value is number => value != null);
  if (showMa20) visibleValues.push(...ma20.filter((value): value is number => value != null));
  if (showMa50) visibleValues.push(...ma50.filter((value): value is number => value != null));
  const min = Math.min(...visibleValues), max = Math.max(...visibleValues), spread = max - min || 1;
  const x = (index: number) => PAD_X + index * ((WIDTH - PAD_X * 2) / Math.max(1, rows.length - 1));
  const y = (value: number) => PRICE_HEIGHT - 18 - ((value - min) / spread) * (PRICE_HEIGHT - 36);
  const volumeMax = Math.max(...rows.map((row) => row.volume_try ?? 0), 1);
  const closePoints = linePoints(rows.map((row) => row.close), x, y);
  const bandPoints = [...rows.map((row, index) => row.low == null ? null : `${x(index)},${y(row.low)}`).filter(Boolean), ...rows.map((row, index) => row.high == null ? null : `${x(index)},${y(row.high)}`).filter(Boolean).reverse()].join(" ");
  const first = rows[0], last = rows.at(-1) ?? first;
  const change = ((last.close / first.close) - 1) * 100;
  const selectedIndex = hovered == null ? rows.length - 1 : hovered;
  const selected = rows[selectedIndex];
  const chartHeight = showRsi ? 480 : 375;

  function handlePointer(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - bounds.left) / bounds.width) * WIDTH;
    const index = Math.round(((svgX - PAD_X) / (WIDTH - PAD_X * 2)) * (rows.length - 1));
    setHovered(Math.max(0, Math.min(rows.length - 1, index)));
  }

  return <div>
    <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"><div className="flex gap-1 overflow-x-auto">{ranges.map((item) => <button key={item.label} onClick={() => { setRangeDays(item.days); setHovered(null); }} className={`rounded-[8px] px-2.5 py-1.5 text-[11px] font-semibold transition ${rangeDays === item.days ? "bg-[var(--primary-soft)] text-[var(--primary)]" : "text-[var(--text-muted)] hover:bg-[var(--surface-hover)]"}`}>{item.label}</button>)}</div><div className="flex flex-wrap gap-1.5"><Toggle active={showMa20} onClick={() => setShowMa20(!showMa20)}>MA20</Toggle><Toggle active={showMa50} onClick={() => setShowMa50(!showMa50)}>MA50</Toggle><Toggle active={showAverage} onClick={() => setShowAverage(!showAverage)}>AOF</Toggle><Toggle active={showRsi} onClick={() => setShowRsi(!showRsi)}>RSI</Toggle></div></div>
    <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4"><MiniMetric label="Seçili kapanış" value={formatMoney(selected.close)}/><MiniMetric label="Dönem değişimi" value={formatPercent(change, true)} tone={change >= 0}/><MiniMetric label="Dönem düşük" value={formatMoney(Math.min(...rows.map((row) => row.low ?? row.close)))}/><MiniMetric label="Dönem yüksek" value={formatMoney(Math.max(...rows.map((row) => row.high ?? row.close)))}/></div>
    <div className="relative"><svg className="h-auto w-full touch-none" viewBox={`0 0 ${WIDTH} ${chartHeight}`} role="img" aria-label={`${rows.length} günlük etkileşimli fiyat ve hacim grafiği`} onPointerMove={handlePointer} onPointerLeave={() => setHovered(null)}>
      <defs><linearGradient id="advancedPriceArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".2"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>
      {[0,.25,.5,.75,1].map((ratio) => <g key={ratio}><line x1={PAD_X} x2={WIDTH-PAD_X} y1={18+ratio*(PRICE_HEIGHT-36)} y2={18+ratio*(PRICE_HEIGHT-36)} stroke="var(--chart-grid)" strokeDasharray="4 5"/><text x={4} y={22+ratio*(PRICE_HEIGHT-36)} fill="var(--text-muted)" fontSize="10">{formatNumber(max-ratio*spread, 1)}</text></g>)}
      {bandPoints && <polygon points={bandPoints} fill="var(--primary-soft)" opacity=".7"/>}<polygon points={`${PAD_X},${PRICE_HEIGHT-18} ${closePoints} ${WIDTH-PAD_X},${PRICE_HEIGHT-18}`} fill="url(#advancedPriceArea)"/>
      {showAverage && <polyline points={linePoints(rows.map((row) => row.avg_price), x, y)} fill="none" stroke="var(--warning)" strokeWidth="1.4" strokeDasharray="5 4"/>}{showMa50 && <polyline points={linePoints(ma50, x, y)} fill="none" stroke="var(--negative)" strokeWidth="1.5"/>}{showMa20 && <polyline points={linePoints(ma20, x, y)} fill="none" stroke="var(--positive)" strokeWidth="1.5"/>}<polyline points={closePoints} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      {rows.map((row, index) => { const height = ((row.volume_try ?? 0) / volumeMax) * VOLUME_HEIGHT; const barWidth = Math.max(.6, 320 / rows.length); return <rect key={row.date} x={x(index)-barWidth/2} y={VOLUME_TOP+VOLUME_HEIGHT-height} width={barWidth} height={height} rx=".7" fill={index && row.close < rows[index-1].close ? "var(--negative)" : "var(--positive)"} opacity=".55"/>; })}<text x={PAD_X} y={VOLUME_TOP-8} fill="var(--text-muted)" fontSize="10">HACİM · tepe {formatMoney(volumeMax, true)}</text>
      {showRsi && <g><line x1={PAD_X} x2={WIDTH-PAD_X} y1={RSI_TOP+RSI_HEIGHT*.3} y2={RSI_TOP+RSI_HEIGHT*.3} stroke="var(--negative)" strokeDasharray="4 5" opacity=".5"/><line x1={PAD_X} x2={WIDTH-PAD_X} y1={RSI_TOP+RSI_HEIGHT*.7} y2={RSI_TOP+RSI_HEIGHT*.7} stroke="var(--positive)" strokeDasharray="4 5" opacity=".5"/><polyline points={linePoints(rsiValues, x, (value) => RSI_TOP+RSI_HEIGHT-(value/100)*RSI_HEIGHT)} fill="none" stroke="var(--warning)" strokeWidth="1.7"/><text x={PAD_X} y={RSI_TOP-8} fill="var(--text-muted)" fontSize="10">RSI (14)</text></g>}
      <line x1={x(selectedIndex)} x2={x(selectedIndex)} y1={14} y2={VOLUME_TOP+VOLUME_HEIGHT} stroke="var(--text-muted)" strokeDasharray="3 4" opacity=".8"/><circle cx={x(selectedIndex)} cy={y(selected.close)} r="4" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2"/><text x={PAD_X} y={chartHeight-3} fill="var(--text-muted)" fontSize="10">{first.date}</text><text x={WIDTH-PAD_X} y={chartHeight-3} textAnchor="end" fill="var(--text-muted)" fontSize="10">{last.date}</text>
    </svg><div className="pointer-events-none absolute right-2 top-2 rounded-[10px] border px-3 py-2 text-[10px] leading-5 shadow-lg" style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--surface) 92%, transparent)" }}><p className="font-semibold text-[var(--text)]">{selected.date}</p><p>Kapanış {formatMoney(selected.close)}</p><p>Min / Maks {formatMoney(selected.low)} / {formatMoney(selected.high)}</p><p>AOF {formatMoney(selected.avg_price)}</p><p>Hacim {formatMoney(selected.volume_try, true)}</p></div></div>
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-[var(--text-muted)]"><Legend color="var(--primary)">Kapanış</Legend><Legend color="var(--primary-soft)">Min–maks bant</Legend>{showMa20 && <Legend color="var(--positive)">MA20</Legend>}{showMa50 && <Legend color="var(--negative)">MA50</Legend>}{showAverage && <Legend color="var(--warning)">AOF</Legend>}<span>{rows.length} işlem günü</span></div>
  </div>;
}

function Toggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) { return <button onClick={onClick} aria-pressed={active} className={`rounded-[8px] border px-2.5 py-1.5 text-[10px] font-semibold transition ${active ? "border-transparent bg-[var(--primary-soft)] text-[var(--primary)]" : "text-[var(--text-muted)]"}`} style={active ? undefined : { borderColor: "var(--border)" }}>{children}</button>; }
function MiniMetric({ label, value, tone }: { label: string; value: string; tone?: boolean }) { return <div className="rounded-[9px] bg-[var(--surface-raised)] px-3 py-2"><p className="text-[9px] uppercase tracking-wider text-[var(--text-muted)]">{label}</p><p className={`mt-1 text-xs font-semibold ${tone === true ? "text-[var(--positive)]" : tone === false ? "text-[var(--negative)]" : ""}`}>{value}</p></div>; }
function Legend({ color, children }: { color: string; children: ReactNode }) { return <span className="flex items-center gap-1.5"><span className="h-1.5 w-3 rounded-full" style={{ background: color }}/>{children}</span>; }
