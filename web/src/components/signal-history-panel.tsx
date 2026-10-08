"use client";

import Link from "next/link";
import { useId, useMemo, useState } from "react";
import { chartDomain, chartPath } from "@/lib/chart-data";
import { formatDate, formatNumber, relativeTime, signalName, componentName } from "@/lib/format";
import { COMPONENT_KEYS, componentSeries, driverKindName, labelChanges, normalizeHistory, scoreDelta } from "@/lib/signal-history";
import type { SignalHistory } from "@/lib/types";
import { chartButton, useChartWidth } from "./chart-frame";
import { EmptyState } from "./ui";

const COLORS = ["var(--primary)", "var(--positive)", "#d99a2b", "var(--negative)"];

function Delta({ label, value }: { label: string; value: number | null }) {
  const tone = value == null || value === 0 ? "" : value > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
  return <div className="rounded border border-[var(--border)] px-3 py-2"><p className="eyebrow">{label}</p><p className={`terminal-mono text-sm font-semibold ${tone}`}>{value == null ? "—" : `${value > 0 ? "+" : ""}${formatNumber(value, 1)}`}</p></div>;
}

export function SignalHistoryPanel({ history, error = false }: { history: SignalHistory; error?: boolean }) {
  const { ref, width } = useChartWidth();
  const id = useId();
  const [mode, setMode] = useState<"composite" | "components">("composite");
  const points = useMemo(() => normalizeHistory(history.points), [history.points]);
  const changes = useMemo(() => labelChanges(points), [points]);
  if (error) return <EmptyState compact title="Skor geçmişi alınamadı" description="Servis geçici olarak yanıt vermiyor; sayfayı yenileyerek tekrar deneyin."/>;
  if (!points.length) return <EmptyState compact title="Skor geçmişi henüz oluşmadı" description="Bileşik skor günlük hesaplandıkça zaman serisi burada görünecek."/>;

  const series = mode === "composite" ? [{ key: "composite", name: "Bileşik skor", values: points.map((p) => p.composite_score) as Array<number | null> }] : COMPONENT_KEYS.map((key) => ({ key, name: componentName(key), values: componentSeries(points, key) }));
  const [min, max] = chartDomain([0, 100, ...series.flatMap((s) => s.values.filter((v): v is number => v != null))]);
  const left = 36, right = width - 12, top = 12, bottom = 168;
  const x = (i: number) => points.length <= 1 ? (left + right) / 2 : left + i * (right - left) / (points.length - 1);
  const y = (v: number) => bottom - ((v - min) / (max - min || 1)) * (bottom - top);
  const last = points[points.length - 1];

  return <div ref={ref} className="min-w-0" data-testid="signal-history">
    <div className="mb-3 grid grid-cols-3 gap-2"><Delta label="1 gün" value={scoreDelta(points, 1)}/><Delta label="7 gün" value={scoreDelta(points, 7)}/><Delta label="30 gün" value={scoreDelta(points, 30)}/></div>
    <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label="Skor görünümü">{([["composite", "Bileşik"], ["components", "Bileşenler"]] as const).map(([value, text]) => <button type="button" key={value} aria-pressed={mode === value} className={`${chartButton} ${mode === value ? "bg-[var(--primary-soft)] !text-[var(--primary)]" : ""}`} onClick={() => setMode(value)}>{text}</button>)}</div>
    <svg role="img" aria-label={`Skor geçmişi, son skor ${formatNumber(last.composite_score, 0)}`} className="w-full" style={{ height: 196 }} viewBox={`0 0 ${width} 196`}>
      <defs><linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".18"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>
      {[0, 25, 50, 75, 100].map((tick) => <g key={tick}><line x1={left} x2={right} y1={y(tick)} y2={y(tick)} stroke="var(--chart-grid)" strokeDasharray="4 5"/><text x={left - 6} y={y(tick) + 3} textAnchor="end" fontSize="10" fill="var(--text-muted)">{tick}</text></g>)}
      {series.map((s, i) => points.length > 1
        ? <g key={s.key}>{mode === "composite" && <path d={`${chartPath(s.values, x, y)} L${x(points.length - 1)},${bottom} L${x(0)},${bottom} Z`} fill={`url(#${id}-area)`}/>}<path d={chartPath(s.values, x, y)} fill="none" stroke={mode === "composite" ? COLORS[0] : COLORS[i]} strokeWidth="2"/></g>
        : s.values[0] != null && <circle key={s.key} cx={x(0)} cy={y(s.values[0]!)} r="3.5" fill={mode === "composite" ? COLORS[0] : COLORS[i]}/>)}
      {changes.map((c) => <g key={c.date}><title>{`${formatDate(c.date)}: ${signalName(c.from)} → ${signalName(c.to)}`}</title><line x1={x(c.index)} x2={x(c.index)} y1={top} y2={bottom} stroke="var(--text-muted)" strokeDasharray="2 4"/><circle cx={x(c.index)} cy={y(c.score)} r="4.5" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2"/></g>)}
      <text x={left} y={190} fontSize="10" fill="var(--text-muted)">{points[0].as_of_date}</text><text x={right} y={190} textAnchor="end" fontSize="10" fill="var(--text-muted)">{last.as_of_date}</text>
    </svg>
    {mode === "components" && <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--text-secondary)]">{COMPONENT_KEYS.map((key, i) => <span key={key} style={{ color: COLORS[i] }}>● {componentName(key)}</span>)}</div>}
    <p className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">Halkalı noktalar etiket değişimini gösterir{changes.length ? `: ${changes.slice(-3).map((c) => `${formatDate(c.date)} ${signalName(c.to)}`).join(" · ")}` : "; seçili aralıkta etiket değişmedi"}. Eksik bileşenler çizgide boşluk bırakır.</p>
  </div>;
}

export function SignalDrivers({ history, error = false }: { history: SignalHistory; error?: boolean }) {
  if (error) return <EmptyState compact title="Skor nedenleri alınamadı"/>;
  if (!history.drivers.length) return <EmptyState compact title="Skoru etkileyen kayıt yok" description="Haber, KAP veya analist verisi bu skora katkı verdiğinde burada kronolojik olarak listelenir."/>;
  return <div className="panel-flat overflow-hidden">{history.drivers.map((item, index) => <Link href={item.href} key={`${item.kind}-${item.href}-${item.occurred_at}-${index}`} className={`flex items-start gap-3 p-4 transition hover:bg-[var(--surface-hover)] ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}>
    <span className={`pill shrink-0 ${item.effect > 0 ? "pill-positive" : item.effect < 0 ? "pill-negative" : ""}`}>{item.effect > 0 ? "+" : ""}{formatNumber(item.effect, 0)}</span>
    <div className="min-w-0 flex-1"><div className="mb-1 flex items-center gap-2 text-[11px] text-[var(--text-muted)]"><span className="eyebrow">{driverKindName(item.kind)}</span>{item.occurred_at && <span>{relativeTime(item.occurred_at)}</span>}</div><p className="line-clamp-2 text-sm font-medium leading-5">{item.title}</p></div></Link>)}</div>;
}
