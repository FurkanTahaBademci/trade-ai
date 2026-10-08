import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { CalendarEvent } from "@/lib/types";
import { EVENT_TYPES, groupByDate, monthRange, parseMonth, parseTypes, shiftMonth } from "@/lib/calendar";
import { formatDate } from "@/lib/format";
import { normalizeTicker } from "@/lib/turkish";
import { EmptyState, PageHeader, ServiceNotice } from "@/components/ui";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "Takvim" };

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

type Params = { month?: string; types?: string; ticker?: string };

function href(month: string, types: string[], ticker: string) {
  const query = new URLSearchParams({ month });
  if (types.length) query.set("types", types.join(","));
  if (ticker) query.set("ticker", ticker);
  return `/takvim?${query}`;
}

export default async function CalendarPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const month = parseMonth(params.month, new Date().toISOString().slice(0, 7));
  const types = parseTypes(params.types);
  const rawTicker = normalizeTicker(params.ticker ?? "");
  const ticker = /^[A-Z0-9]{1,16}$/.test(rawTicker) ? rawTicker : "";
  const { start, end } = monthRange(month);
  const query = new URLSearchParams({ start, end });
  for (const type of types) query.append("types", type);
  if (ticker) query.set("ticker", ticker);
  const result = await apiGet<CalendarEvent[]>(`/api/calendar?${query}`, []);
  const groups = groupByDate(result.data);
  const [year, mon] = month.split("-").map(Number);
  const today = new Date().toISOString().slice(0, 10);

  return <><PageHeader eyebrow="Türkiye · Olay takvimi" title="Piyasa Takvimi" description="TCMB PPK toplantıları ile KAP bildirimlerinden türetilen finansal rapor, temettü, genel kurul ve sermaye artırımı olayları. KAP olayları bildirimin yayın tarihine göre gösterilir." actions={<div className="flex flex-wrap items-center gap-2">
    <Link href={href(shiftMonth(month, -1), types, ticker)} className="pill" aria-label="Önceki ay">←</Link>
    <span className="pill pill-primary"><Icon name="calendar" size={12}/>{MONTHS[mon - 1]} {year}</span>
    <Link href={href(shiftMonth(month, 1), types, ticker)} className="pill" aria-label="Sonraki ay">→</Link>
    <span className="mx-1 h-4 w-px bg-[var(--border)]"/>
    <Link href={href(month, [], ticker)} className={`pill transition ${types.length === 0 ? "pill-primary" : "hover:text-[var(--text)]"}`}>Tümü</Link>
    {EVENT_TYPES.map((item) => { const active = types.includes(item.value); const next = active ? types.filter((t) => t !== item.value) : [...types, item.value]; return <Link key={item.value} href={href(month, next, ticker)} aria-pressed={active} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{item.label}</Link>; })}
  </div>}/>
    <form action="/takvim" className="mb-4 flex flex-wrap items-center gap-2">
      <input type="hidden" name="month" value={month}/>{types.length > 0 && <input type="hidden" name="types" value={types.join(",")}/>}
      <input name="ticker" defaultValue={ticker} placeholder="Hisse kodu (ör. THYAO)" aria-label="Hisse kodu" maxLength={16} className="h-9 w-56 rounded border bg-transparent px-3 text-xs outline-none placeholder:text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}/>
      <button type="submit" className="rounded border px-3 py-2 text-xs" style={{ borderColor: "var(--border)" }}>Filtrele</button>
      {ticker && <Link href={href(month, types, "")} className="text-xs text-[var(--text-muted)]">Hisse filtresini temizle</Link>}
    </form>
    <ServiceNotice show={!result.ok}/>
    {groups.length ? <div className="space-y-4">{groups.map(([date, events]) => <section key={date} className="panel-flat overflow-hidden">
      <div className="flex items-center gap-2 border-b px-4 py-2.5" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}><span className="terminal-mono text-xs font-semibold">{formatDate(date)}</span>{date === today && <span className="pill pill-primary">Bugün</span>}<span className="ml-auto text-[10px] text-[var(--text-muted)]">{events.length} olay</span></div>
      {events.map((event, index) => { const tone = EVENT_TYPES.find((t) => t.value === event.type)?.tone ?? ""; return <div key={event.id} className={`flex flex-wrap items-center gap-3 px-4 py-3 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}>
        <span className={`pill ${tone}`}>{event.type_label}</span>
        <div className="min-w-0 flex-1"><p className="line-clamp-2 text-sm font-medium">{event.title}</p>{event.detail && <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{event.detail}{event.upcoming ? " · Yaklaşan" : ""}</p>}{!event.detail && event.upcoming && <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Yaklaşan</p>}</div>
        <div className="flex flex-wrap items-center gap-2">{event.tickers.map((code) => <Link key={code} href={`/piyasalar/${code}`} className="terminal-mono text-xs font-semibold text-[var(--primary)]">{code}</Link>)}{event.disclosure_index != null && <Link href={`/kap/${event.disclosure_index}`} className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--primary)]">KAP #{event.disclosure_index} <Icon name="arrow" size={12}/></Link>}</div>
      </div>; })}
    </section>)}</div> : <div className="panel-flat"><EmptyState title="Bu ay için olay bulunamadı" description="Filtreleri temizleyin veya başka bir ay seçin."/></div>}
    <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Olay türleri KAP başlık/konu alanlarındaki kurallarla belirlenir; kesin tarih ve koşullar için bildirimin kendisine bakın. Yatırım tavsiyesi değildir.</p>
  </>;
}
