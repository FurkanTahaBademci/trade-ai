"use client";

import { useId, useMemo, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { chartDomain, chartPath, movingAverage, normalizePrices, rangeStart, wilderRsi } from "@/lib/chart-data";
import type { Price } from "@/lib/types";
import { chartButton, useChartWidth } from "./chart-frame";

const TOP = 16, BOTTOM = 246, VOLUME_TOP = 278, VOLUME_BOTTOM = 338, RSI_TOP = 376, RSI_BOTTOM = 446;
const ranges = [{ label: "1A", days: 30 }, { label: "3A", days: 90 }, { label: "6A", days: 180 }, { label: "1Y", days: 365 }, { label: "3Y", days: 1095 }, { label: "Tümü", days: 0 }];

export function PriceChart({ prices, error = false }: { prices: Price[]; error?: boolean }) {
  const { ref, width } = useChartWidth();
  const id = useId();
  const [rangeDays, setRangeDays] = useState<number | null>(90);
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [mode, setMode] = useState<"line" | "hlc">("line");
  const [showMa20, setShowMa20] = useState(true);
  const [showMa50, setShowMa50] = useState(false);
  const [showAverage, setShowAverage] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const all = useMemo(() => {
    const normalized = normalizePrices(prices), closes = normalized.map((row) => row.close);
    const ma20 = movingAverage(closes, 20), ma50 = movingAverage(closes, 50), rsi = wilderRsi(closes);
    return normalized.map((row, i) => ({ ...row, ma20: ma20[i], ma50: ma50[i], rsi: rsi[i] }));
  }, [prices]);
  const start = rangeDays === null ? custom.start : rangeDays && all.length ? rangeStart(all.at(-1)!.date, rangeDays) : all[0]?.date ?? "";
  const end = rangeDays === null ? custom.end : all.at(-1)?.date ?? "";
  const invalidRange = !!start && !!end && start > end;
  const rows = useMemo(() => invalidRange ? [] : all.filter((row) => (!start || row.date >= start) && (!end || row.date <= end)), [all, start, end, invalidRange]);
  const foundIndex = selectedDate == null ? -1 : rows.findIndex((row) => row.date === selectedDate);
  const index = foundIndex < 0 ? Math.max(0, rows.length - 1) : foundIndex;
  const selected = rows[index], first = rows[0], last = rows.at(-1);
  const left = 60, right = width - 14;
  const x = (i: number) => rows.length <= 1 ? (left + right) / 2 : left + i * (right - left) / Math.max(1, rows.length - 1);
  const visibleValues = rows.flatMap((row) => [row.close, row.low, row.high, showAverage ? row.avg_price : null, showMa20 ? row.ma20 : null, showMa50 ? row.ma50 : null]).filter((value): value is number => value != null && Number.isFinite(value));
  const [min, max] = chartDomain(visibleValues);
  const y = (value: number) => {
    const range = max - min;
    if (range <= 0 || !Number.isFinite(range)) return (TOP + BOTTOM) / 2;
    return BOTTOM - ((value - min) / range) * (BOTTOM - TOP);
  };
  const volumeMax = rows.reduce((peak, row) => Math.max(peak, row.volume_try ?? 0), 0);
  const hasVolume = rows.some((row) => row.volume_try != null && row.volume_try > 0);
  const path = chartPath(rows.map((row) => row.close), x, y);
  const change = first && last && rows.length > 1 ? (last.close / first.close - 1) * 100 : null;
  const height = showRsi ? 468 : 360;

  function selectPreset(days: number) { setRangeDays(days); setSelectedDate(null); }
  function selectCustom(name: "start" | "end", value: string) {
    setCustom({ start, end, [name]: value }); setRangeDays(null); setSelectedDate(null);
  }
  function zoom(factor: number) {
    if (rows.length < 2) return;
    const lastIndex = all.findIndex((row) => row.date === last!.date);
    const count = Math.min(all.length, Math.max(2, Math.round(rows.length * factor)));
    const firstIndex = Math.max(0, lastIndex - count + 1);
    setCustom({ start: all[firstIndex].date, end: all[Math.min(all.length - 1, firstIndex + count - 1)].date });
    setRangeDays(null); setSelectedDate(null);
  }
  function moveWindow(direction: number) {
    if (!rows.length) return;
    const offset = Math.max(1, Math.floor(rows.length / 2)) * direction;
    const firstIndex = Math.max(0, Math.min(all.length - rows.length, all.findIndex((row) => row.date === first.date) + offset));
    setCustom({ start: all[firstIndex].date, end: all[firstIndex + rows.length - 1].date }); setRangeDays(null); setSelectedDate(null);
  }
  function handlePointer(event: PointerEvent<SVGSVGElement>) {
    if (rows.length <= 1) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const svgX = (event.clientX - bounds.left) * width / bounds.width;
    const i = Math.max(0, Math.min(rows.length - 1, Math.round((svgX - left) / (right - left) * (rows.length - 1))));
    setSelectedDate(rows[i]?.date ?? null);
  }
  function handleKey(event: KeyboardEvent<SVGSVGElement>) {
    if (rows.length <= 1) return;
    const next = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: rows.length - 1 }[event.key];
    if (next == null) return;
    event.preventDefault(); setSelectedDate(rows[Math.max(0, Math.min(rows.length - 1, next))]?.date ?? null);
  }

  return <div ref={ref} className="min-w-0" data-testid="price-chart">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-1" role="group" aria-label="Grafik dönemi">{ranges.map((item) => <Toggle key={item.label} active={rangeDays === item.days} onClick={() => selectPreset(item.days)}>{item.label}</Toggle>)}</div>
      <div className="flex gap-1" role="group" aria-label="Grafik türü"><Toggle active={mode === "line"} onClick={() => setMode("line")}>Çizgi</Toggle><Toggle active={mode === "hlc"} onClick={() => setMode("hlc")}>Düşük–yüksek–kapanış</Toggle></div>
    </div>
    <div className="mb-3 grid grid-cols-2 items-end gap-2 sm:flex sm:flex-wrap">
      <label className="min-w-0 flex-1 text-xs text-[var(--text-muted)]">Başlangıç<input aria-label="Grafik başlangıcı" className="input mt-1 min-w-0" type="date" value={start} onChange={(event) => selectCustom("start", event.target.value)}/></label>
      <label className="min-w-0 flex-1 text-xs text-[var(--text-muted)]">Bitiş<input aria-label="Grafik bitişi" className="input mt-1 min-w-0" type="date" value={end} onChange={(event) => selectCustom("end", event.target.value)}/></label>
      <div className="col-span-2 flex gap-1"><button type="button" className={chartButton} aria-label="Önceki dönem" disabled={!first || first.date === all[0]?.date} onClick={() => moveWindow(-1)}>←</button><button type="button" className={chartButton} aria-label="Yakınlaştır" disabled={rows.length <= 2} onClick={() => zoom(.5)}>+</button><button type="button" className={chartButton} aria-label="Uzaklaştır" disabled={rows.length < 2 || rows.length === all.length} onClick={() => zoom(2)}>−</button><button type="button" className={chartButton} aria-label="Sonraki dönem" disabled={!last || last.date === all.at(-1)?.date} onClick={() => moveWindow(1)}>→</button></div>
    </div>
    <div className="mb-4 flex flex-wrap gap-1.5"><Toggle active={showMa20} onClick={() => setShowMa20(!showMa20)}>MA20</Toggle><Toggle active={showMa50} onClick={() => setShowMa50(!showMa50)}>MA50</Toggle><Toggle active={showAverage} onClick={() => setShowAverage(!showAverage)}>AOF</Toggle><Toggle active={showRsi} onClick={() => setShowRsi(!showRsi)}>RSI (14)</Toggle></div>
    {!selected ? <p role="status" className="grid h-52 place-items-center text-center text-sm text-[var(--text-muted)]">{error ? "Fiyat servisine ulaşılamadı. Sayfayı yenileyerek tekrar deneyin." : invalidRange ? "Bitiş tarihi başlangıçtan önce olamaz." : all.length ? "Bu tarih aralığında fiyat yok. Başka bir aralık seçin." : "Grafik için fiyat verisi bekleniyor."}</p> : <>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4"><MiniMetric label="Seçili kapanış" value={formatMoney(selected.close)}/><MiniMetric label="Dönem değişimi" value={formatPercent(change, true)}/><MiniMetric label="Dönem düşük" value={formatMoney(Math.min(...rows.map((row) => row.low ?? row.close)))}/><MiniMetric label="Dönem yüksek" value={formatMoney(Math.max(...rows.map((row) => row.high ?? row.close)))}/></div>
      <svg className="w-full touch-pan-y rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]" style={{ height }} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} aria-label="Etkileşimli hisse fiyat ve hacim grafiği" aria-describedby={`${id}-help`} onPointerMove={handlePointer} onPointerDown={handlePointer} onPointerLeave={() => setSelectedDate(null)} onKeyDown={handleKey}>
        <defs><linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--primary)" stopOpacity=".18"/><stop offset="1" stopColor="var(--primary)" stopOpacity="0"/></linearGradient></defs>
        {[0,.25,.5,.75,1].map((ratio) => <g key={ratio}><line x1={left} x2={right} y1={TOP+ratio*(BOTTOM-TOP)} y2={TOP+ratio*(BOTTOM-TOP)} stroke="var(--chart-grid)" strokeDasharray="4 5"/><text x={left-8} textAnchor="end" y={TOP+4+ratio*(BOTTOM-TOP)} fill="var(--text-muted)" fontSize="10">{formatNumber(max-ratio*(max-min), 2)}</text></g>)}
        {mode === "line" ? (
          rows.length > 1 ? <>
            <path d={`${path} L${x(rows.length-1)},${BOTTOM} L${x(0)},${BOTTOM} Z`} fill={`url(#${id}-area)`}/>
            <path d={path} fill="none" stroke="var(--primary)" strokeWidth="2"/>
          </> : <line x1={left} x2={right} y1={y(selected.close)} y2={y(selected.close)} stroke="var(--primary)" strokeWidth="2" strokeDasharray="4 4"/>
        ) : rows.map((row, i) => <g key={row.date} stroke={i > 0 && row.close < rows[i-1].close ? "var(--negative)" : "var(--positive)"} strokeWidth="1.5">
          {row.low != null && row.high != null && <line x1={x(i)} x2={x(i)} y1={y(row.low)} y2={y(row.high)}/>}
          <line x1={x(i)} x2={x(i)+Math.max(1, Math.min(6,(right-left)/Math.max(1, rows.length)*.35))} y1={y(row.close)} y2={y(row.close)}/>
        </g>)}
        {[[showMa20, "ma20", "var(--positive)"], [showMa50, "ma50", "var(--negative)"], [showAverage, "avg_price", "var(--warning)"]].map(([show, key, color]) => show && <path key={String(key)} data-series={String(key)} d={chartPath(rows.map((row) => row[key as "ma20" | "ma50" | "avg_price"]), x, y)} fill="none" stroke={String(color)} strokeWidth="1.4" strokeDasharray={key === "avg_price" ? "5 4" : undefined}/>)}
        <text x={left} y={VOLUME_TOP-9} fill="var(--text-muted)" fontSize="10">{hasVolume ? `HACİM (TL) · tepe ${formatMoney(volumeMax, true)}` : "HACİM VERİSİ YOK"}</text>
        {rows.map((row, i) => row.volume_try != null && <rect key={row.date} x={x(i)-Math.max(1,(right-left)/Math.max(1, rows.length)*.55)/2} y={VOLUME_BOTTOM-(volumeMax ? row.volume_try/volumeMax : 0)*(VOLUME_BOTTOM-VOLUME_TOP)} width={Math.max(1,(right-left)/Math.max(1, rows.length)*.55)} height={Math.max(1, (volumeMax ? row.volume_try/volumeMax : 0)*(VOLUME_BOTTOM-VOLUME_TOP))} fill={i > 0 && row.close < rows[i-1].close ? "var(--negative)" : "var(--positive)"} opacity=".55"/>)}
        {showRsi && <g><text x={left} y={RSI_TOP-10} fill="var(--text-muted)" fontSize="10">RSI (14) · Wilder</text>{[30,70].map((level) => <g key={level}><line x1={left} x2={right} y1={RSI_BOTTOM-level/100*(RSI_BOTTOM-RSI_TOP)} y2={RSI_BOTTOM-level/100*(RSI_BOTTOM-RSI_TOP)} stroke="var(--chart-grid)" strokeDasharray="4 5"/><text x={left-8} textAnchor="end" y={RSI_BOTTOM-level/100*(RSI_BOTTOM-RSI_TOP)+4} fill="var(--text-muted)" fontSize="10">{level}</text></g>)}<path data-series="rsi" d={chartPath(rows.map((row) => row.rsi), x, (value) => RSI_BOTTOM-value/100*(RSI_BOTTOM-RSI_TOP))} fill="none" stroke="var(--warning)" strokeWidth="1.5"/></g>}
        <line x1={x(index)} x2={x(index)} y1={TOP} y2={showRsi ? RSI_BOTTOM : VOLUME_BOTTOM} stroke="var(--text-muted)" strokeDasharray="3 4"/><circle cx={x(index)} cy={y(selected.close)} r="4" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2.5"/>
        <text x={left} y={height-3} fill="var(--text-muted)" fontSize="10">{first.date}</text><text x={right} y={height-3} textAnchor="end" fill="var(--text-muted)" fontSize="10">{last?.date}</text>
      </svg>
      {rows.length > 1 && <label className="mt-2 block text-xs text-[var(--text-muted)]">İşlem günü seç<input aria-label="İşlem günü seç" className="mt-1 block w-full accent-[var(--primary)]" type="range" min={0} max={Math.max(0, rows.length-1)} value={index} disabled={rows.length < 2} aria-valuetext={`${formatDate(selected.date)} · ${formatMoney(selected.close)}`} onChange={(event) => setSelectedDate(rows[Number(event.target.value)].date)}/></label>}
      <div className="mt-3 rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-3" data-testid="price-selection">
        <p className="mb-2 text-xs font-semibold">{formatDate(selected.date)}</p><dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3"><Detail label="Kapanış" value={formatMoney(selected.close)}/><Detail label="Düşük / Yüksek" value={`${formatMoney(selected.low)} / ${formatMoney(selected.high)}`}/><Detail label="Hacim (TL)" value={formatMoney(selected.volume_try, true)}/>{showMa20 && <Detail label="MA20" value={formatMoney(selected.ma20)}/>} {showMa50 && <Detail label="MA50" value={formatMoney(selected.ma50)}/>} {showAverage && <Detail label="AOF" value={formatMoney(selected.avg_price)}/>} {showRsi && <Detail label="RSI (14)" value={formatNumber(selected.rsi, 2)}/>}</dl>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--text-muted)]" aria-label="Gösterge renkleri"><span className="text-[var(--primary)]">● Kapanış</span>{showMa20 && <span className="text-[var(--positive)]">● MA20</span>}{showMa50 && <span className="text-[var(--negative)]">● MA50</span>}{showAverage && <span className="text-[var(--warning)]">┄ AOF</span>}{showRsi && <span className="text-[var(--warning)]">● RSI (alt panel)</span>}</div>
      {mode === "hlc" && <p className="mt-2 text-xs text-[var(--text-muted)]">Dikey çubuk düşük–yüksek, sağ çizgi kapanıştır. Açılış verisi bulunmadığından mum grafik değildir.</p>}
      {((showMa20 && rows.some((row) => row.ma20 == null)) || (showMa50 && rows.some((row) => row.ma50 == null)) || (showRsi && rows.some((row) => row.rsi == null))) && <p className="mt-2 text-xs text-[var(--text-muted)]">Yeterli geçmiş olmayan günlerde gösterge çizilmez. MA20/MA50 için 20/50, RSI için 15 kapanış gerekir.</p>}
      <p className="mt-2 text-xs text-[var(--text-muted)]">{rows.length} işlem günü · Son kayıt {all.at(-1)?.date} · Gün sonu verisi, canlı fiyat değildir.</p>
    </>}
    <p id={`${id}-help`} className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">Grafikte dokunarak veya ← → tuşlarıyla gün seçin; Home/End ilk/son güne gider. Tarihler ve +/− ile yakınlaştırın. Göstergeler seçili aralıktan önceki mevcut geçmişi de kullanır.</p>
  </div>;
}

function Toggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button type="button" onClick={onClick} aria-pressed={active} className={`${chartButton} ${active ? "border-transparent bg-[var(--primary-soft)] !text-[var(--primary)]" : ""}`}>{children}</button>;
}
function MiniMetric({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-[var(--surface-raised)] px-3 py-2"><p className="text-[10px] text-[var(--text-muted)]">{label}</p><p className="mt-1 text-xs font-semibold">{value}</p></div>; }
function Detail({ label, value }: { label: string; value: string }) { return <div><dt className="text-[var(--text-muted)]">{label}</dt><dd className="mt-1 font-medium">{value}</dd></div>; }
