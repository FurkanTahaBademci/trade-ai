"use client";

import { useId, useMemo, useState } from "react";
import { benchmarkChangeSeries, chartDomain, chartPath, performanceSeries, rangeStart, type ValuePoint } from "@/lib/chart-data";
import { formatDate, formatMoney, formatPercent } from "@/lib/format";
import { chartButton, useChartWidth } from "./chart-frame";

type Mode = "value" | "change" | "drawdown";
const modes: { value: Mode; label: string }[] = [{ value: "value", label: "Portföy değeri" }, { value: "change", label: "Dönem değişimi (%)" }, { value: "drawdown", label: "Zirveden düşüş (%)" }];

export function PerformanceChart({ source, label, benchmark, benchmarkLabel = "BIST100" }: { source: ValuePoint[]; label: string; benchmark?: ValuePoint[]; benchmarkLabel?: string }) {
  const { ref, width } = useChartWidth();
  const id = useId();
  const [days, setDays] = useState(0);
  const [mode, setMode] = useState<Mode>("value");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const all = useMemo(() => performanceSeries(source), [source]);
  const rows = useMemo(() => !days || !all.length ? all : all.filter((row) => row.date >= rangeStart(all.at(-1)!.date, days)), [all, days]);
  const found = selectedDate == null ? -1 : rows.findIndex((row) => row.date === selectedDate);
  const index = found < 0 ? Math.max(0, rows.length - 1) : found;
  const selected = rows[index], first = rows[0];
  const values = rows.map((row) => mode === "value" ? row.value : mode === "drawdown" ? row.drawdown : first.value > 0 ? (row.value / first.value - 1) * 100 : null);
  const benchmarkValues = mode === "change" && benchmark?.length ? benchmarkChangeSeries(rows.map((row) => row.date), benchmark) : null;
  const [min, max] = chartDomain([
    ...values.filter((value): value is number => value != null),
    ...(benchmarkValues?.filter((value): value is number => value != null) ?? []),
    ...(mode === "drawdown" ? [0] : []),
  ]);
  const left = 72, right = width - 14, top = 18, bottom = 228;
  const x = (i: number) => left + i * (right - left) / Math.max(1, rows.length - 1);
  const y = (value: number) => bottom - (value - min) / (max - min) * (bottom - top);
  const format = (value: number | null) => mode === "value" ? formatMoney(value, true) : formatPercent(value, true);
  const color = mode === "drawdown" ? "var(--negative)" : "var(--primary)";
  const line = chartPath(values, x, y);
  const benchmarkLine = benchmarkValues ? chartPath(benchmarkValues, x, y) : null;
  const select = (i: number) => setSelectedDate(rows[Math.max(0, Math.min(rows.length - 1, i))]?.date ?? null);

  return <div ref={ref} className="min-w-0" data-testid="performance-chart">
    <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label={`${label} görünümü`}>{modes.map((item) => <button type="button" key={item.value} aria-pressed={mode === item.value} className={`${chartButton} ${mode === item.value ? "bg-[var(--primary-soft)] !text-[var(--primary)]" : ""}`} onClick={() => setMode(item.value)}>{item.label}</button>)}</div>
    <div className="mb-4 flex flex-wrap gap-1" role="group" aria-label={`${label} dönemi`}>{[[30,"1A"], [90,"3A"], [365,"1Y"], [0,"Tümü"]].map(([value, text]) => <button type="button" key={value} aria-pressed={days === value} className={`${chartButton} ${days === value ? "bg-[var(--primary-soft)] !text-[var(--primary)]" : ""}`} onClick={() => { setDays(Number(value)); setSelectedDate(null); }}>{text}</button>)}</div>
    {rows.length < 2 ? <p role="status" className="grid h-52 place-items-center text-center text-xs text-[var(--text-muted)]">Bu aralıkta grafik için en az iki değerleme günü gerekiyor.</p> : mode === "change" && first.value === 0 ? <p role="status" className="grid h-52 place-items-center text-center text-xs text-[var(--text-muted)]">Dönem başlangıç değeri sıfır olduğu için yüzdesel değişim hesaplanamıyor.</p> : <>
      <div className="mb-2 flex flex-wrap justify-between gap-2 text-xs"><span className="text-[var(--text-muted)]">{formatDate(selected.date)}</span><span className="flex items-center gap-3"><span className="font-semibold" data-testid="performance-value">{format(values[index])}</span>{benchmarkValues && <span className="text-[var(--text-muted)]" data-testid="benchmark-value">{benchmarkLabel} {formatPercent(benchmarkValues[index], true)}</span>}</span></div>
      <svg role="img" aria-label={label} aria-describedby={`${id}-help`} tabIndex={0} className="w-full touch-pan-y rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]" style={{ height: 252 }} viewBox={`0 0 ${width} 252`}
        onPointerMove={(event) => { const bounds = event.currentTarget.getBoundingClientRect(); select(Math.round(((event.clientX - bounds.left) * width / bounds.width - left) / (right - left) * (rows.length - 1))); }}
        onPointerLeave={() => setSelectedDate(null)} onKeyDown={(event) => { const next = { ArrowLeft: index-1, ArrowRight: index+1, Home: 0, End: rows.length-1 }[event.key]; if (next != null) { event.preventDefault(); select(next); } }}>
        <defs><linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".18"/><stop offset="1" stopColor={color} stopOpacity="0"/></linearGradient></defs>
        {[0,.25,.5,.75,1].map((ratio) => <g key={ratio}><line x1={left} x2={right} y1={top+ratio*(bottom-top)} y2={top+ratio*(bottom-top)} stroke="var(--chart-grid)" strokeDasharray="4 5"/><text x={left-8} y={top+4+ratio*(bottom-top)} textAnchor="end" fontSize="10" fill="var(--text-muted)">{format(max-ratio*(max-min))}</text></g>)}
        {mode !== "value" && min <= 0 && max >= 0 && <line x1={left} x2={right} y1={y(0)} y2={y(0)} stroke="var(--text-muted)" strokeDasharray="3 4"/>}
        <path d={`${line} L${x(rows.length-1)},${mode === "drawdown" ? y(0) : bottom} L${x(0)},${mode === "drawdown" ? y(0) : bottom} Z`} fill={`url(#${id}-area)`}/>
        <path d={line} fill="none" stroke={color} strokeWidth="2"/>
        {benchmarkLine && <path data-series="benchmark" d={benchmarkLine} fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeDasharray="5 4"/>}
        <line x1={x(index)} x2={x(index)} y1={top} y2={bottom} stroke="var(--text-muted)" strokeDasharray="3 4"/>
        <circle cx={x(index)} cy={y(values[index]!)} r="3.5" fill="var(--surface)" stroke={color} strokeWidth="2"/>
        {benchmarkValues?.[index] != null && <circle cx={x(index)} cy={y(benchmarkValues[index]!)} r="3" fill="var(--surface)" stroke="var(--text-muted)" strokeWidth="1.5"/>}
        <text x={left} y={248} fontSize="10" fill="var(--text-muted)">{first.date}</text><text x={right} y={248} textAnchor="end" fontSize="10" fill="var(--text-muted)">{rows.at(-1)?.date}</text>
      </svg>
      <input aria-label={`${label} günü`} type="range" min={0} max={rows.length-1} value={index} aria-valuetext={`${selected.date} · ${format(values[index])}`} className="mt-2 w-full accent-[var(--primary)]" onChange={(event) => select(Number(event.target.value))}/>
      {benchmarkLine && <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--text-muted)]" aria-label="Gösterge renkleri"><span className="text-[var(--primary)]">● Strateji</span><span>┄ {benchmarkLabel}</span></div>}
    </>}
    <p id={`${id}-help`} className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">{mode === "drawdown" ? "Düşüş, yüklenen tüm geçmişin o güne kadarki en yüksek değerine göredir; dönem değişince geçmiş zirve sıfırlanmaz." : mode === "change" ? `Değişim, seçili dönemin ilk portföy değerine göredir; para giriş/çıkışından arındırılmış getiri değildir.${benchmarkLine ? ` ${benchmarkLabel} çizgisi de aynı ilk günden başlayan gerçek endeks getirisidir.` : ""}` : "Gün sonu portföy değerleri gösterilir."} Grafikte ← → veya alttaki kaydırıcıyla gün seçin.</p>
  </div>;
}
