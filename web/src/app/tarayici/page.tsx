import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { ScreenerResult, ScreenerRow } from "@/lib/types";
import { formatDate, formatMoney, formatNumber, formatPercent, signalName } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice } from "@/components/ui";
import { Icon } from "@/components/icon";
import { MARKET_CAP_OPTIONS, SCREENER_PRESETS, SIGNAL_GROUPS, activeFilterCount, parseScreenerParams, screenerApiQuery, screenerHref, sortHref, type ScreenerParams, type ScreenerSort } from "@/lib/screener";

export const metadata: Metadata = {
  title: "Hisse Tarayıcı",
  description: "BIST hisselerini bileşik skor, F/K, PD/DD, kârlılık, büyüme, momentum ve analist potansiyeline göre filtreleyin.",
};

const PAGE_LIMIT = 200;

const COLUMNS: { key: ScreenerSort; label: string; title?: string }[] = [
  { key: "ticker", label: "Hisse" },
  { key: "change_1d_pct", label: "Gün" },
  { key: "change_1m_pct", label: "1 ay" },
  { key: "market_cap_try", label: "Piy. değeri" },
  { key: "composite_score", label: "Skor" },
  { key: "pe_ratio", label: "F/K", title: "Son 12 ay net kârıyla" },
  { key: "pb_ratio", label: "PD/DD" },
  { key: "roe_pct", label: "ROE" },
  { key: "revenue_yoy_pct", label: "Gelir büy.", title: "Son dönem, yıllık" },
  { key: "upside_pct", label: "Analist pot.", title: "Konsensüs hedef fiyata göre" },
];

export default async function ScreenerPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = parseScreenerParams(await searchParams);
  const result = await apiGet<ScreenerResult | null>(`/api/markets/screener?${screenerApiQuery(params, PAGE_LIMIT)}`, null, { revalidate: 60 });
  const data = result.data;
  const filterCount = activeFilterCount(params);
  return <>
    <PageHeader eyebrow="BIST · Çok kriterli filtre" title="Hisse Tarayıcı" description="Bileşik skor, değerleme, kârlılık, büyüme, momentum ve analist potansiyeline göre tüm BIST evrenini tarayın. Her tarama adres çubuğundan paylaşılabilir." actions={<a href={`/api/export/screener?${screenerApiQuery(params, 1000)}`} download className="pill transition hover:text-[var(--text)]"><Icon name="download" size={12}/>CSV indir</a>}/>
    <ServiceNotice show={!result.ok}/>
    <nav aria-label="Hazır taramalar" className="mb-4 flex flex-wrap gap-2">{SCREENER_PRESETS.map((preset) => { const href = screenerHref(preset.params); const active = href === screenerHref(params); return <Link key={preset.label} href={href} title={preset.description} aria-current={active ? "page" : undefined} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{preset.label}</Link>; })}</nav>
    <form action="/tarayici" method="get" className="panel-flat mb-5 grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
      <Field label="Hisse veya şirket" className="col-span-2 sm:col-span-1"><input name="q" defaultValue={params.q} className="input" placeholder="Kod veya ad" autoComplete="off"/></Field>
      <Field label="Sektör"><select name="sector" defaultValue={params.sector ?? ""} className="input"><option value="">Tüm sektörler</option>{(data?.sectors ?? []).map((sector) => <option key={sector} value={sector}>{sector}</option>)}</select></Field>
      <Field label="Sinyal"><select name="signal" defaultValue={params.signal ?? ""} className="input"><option value="">Tümü</option>{Object.entries(SIGNAL_GROUPS).map(([value, group]) => <option key={value} value={value}>{group.label}</option>)}</select></Field>
      <Field label="Piyasa değeri"><select name="min_market_cap" defaultValue={params.min_market_cap ?? ""} className="input"><option value="">Tümü</option>{MARKET_CAP_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>
      <NumberField params={params} name="min_score" label="Min. bileşik skor" placeholder="ör. 60"/>
      <NumberField params={params} name="max_pe" label="Maks. F/K" placeholder="ör. 10"/>
      <NumberField params={params} name="max_pb" label="Maks. PD/DD" placeholder="ör. 1,5"/>
      <NumberField params={params} name="min_roe" label="Min. ROE (%)" placeholder="ör. 25"/>
      <NumberField params={params} name="min_revenue_growth" label="Min. gelir büyümesi (%)" placeholder="ör. 30"/>
      <NumberField params={params} name="min_upside" label="Min. analist potansiyeli (%)" placeholder="ör. 20"/>
      <NumberField params={params} name="min_change_1m" label="Min. 1 ay getiri (%)" placeholder="ör. 5"/>
      {params.sort !== "composite_score" && <input type="hidden" name="sort" value={params.sort}/>}
      {params.order !== "desc" && <input type="hidden" name="order" value={params.order}/>}
      <div className="col-span-2 flex items-end gap-2 sm:col-span-1"><button type="submit" className="h-10 flex-1 rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Tara</button>{filterCount > 0 && <Link href="/tarayici" className="pill h-10 transition hover:text-[var(--text)]">Sıfırla</Link>}</div>
    </form>
    {data && <p className="mb-3 text-xs text-[var(--text-muted)]" role="status"><strong className="text-[var(--text)]">{formatNumber(data.matched, 0)}</strong> / {formatNumber(data.total, 0)} hisse eşleşti{data.as_of_date ? ` · fiyatlar ${formatDate(data.as_of_date)}` : ""}{data.matched > data.rows.length ? ` · ilk ${data.rows.length} gösteriliyor, tamamı için CSV indirin` : ""}</p>}
    {data?.rows.length ? <div className="table-shell overflow-x-auto"><table className="data-table min-w-[980px]"><caption className="sr-only">Tarama sonuçları</caption><thead><tr>{COLUMNS.map((column) => <th key={column.key} scope="col" title={column.title} aria-sort={params.sort === column.key ? (params.order === "asc" ? "ascending" : "descending") : undefined} className={column.key === "ticker" ? "" : "text-right"}><Link href={sortHref(params, column.key)} scroll={false} className="inline-flex items-center gap-1 hover:text-[var(--text)]">{column.label}{params.sort === column.key && <span aria-hidden="true">{params.order === "asc" ? "↑" : "↓"}</span>}</Link></th>)}</tr></thead><tbody>{data.rows.map((row) => <ResultRow key={row.ticker} row={row}/>)}</tbody></table></div>
      : <div className="panel-flat"><EmptyState title={result.ok ? "Eşleşen hisse yok" : "Tarama sonuçları alınamadı"} description={result.ok ? "Filtreleri gevşetin veya hazır taramalardan birini deneyin. Değeri bilinmeyen hisseler o kritere uymuş sayılmaz." : "Veri servisine ulaşılamadı; biraz sonra tekrar deneyin."}/></div>}
    <p className="mt-4 text-[11px] leading-5 text-[var(--text-muted)]">F/K son 12 ay net kârıyla, PD/DD son bilançodaki özsermayeyle hesaplanır; zarar eden veya özsermayesi negatif şirketlerde gösterilmez. Gelir büyümesi ve ROE son açıklanan döneme aittir. Bir kritere filtre verildiğinde o değeri bilinmeyen hisseler listeden çıkar. Tarama sonuçları bilgi amaçlıdır; yatırım tavsiyesi değildir.</p>
  </>;
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  // Uzun etiketler iki satıra kaysa da kutular aynı hizada kalsın.
  return <label className={`flex min-w-0 flex-col justify-end ${className}`}><span className="eyebrow mb-1.5 block">{label}</span>{children}</label>;
}

function NumberField({ params, name, label, placeholder }: { params: ScreenerParams; name: keyof ScreenerParams; label: string; placeholder?: string }) {
  return <Field label={label}><input name={name} defaultValue={params[name] ?? ""} inputMode="decimal" className="input" placeholder={placeholder} autoComplete="off"/></Field>;
}

function tone(value: number | null) {
  return value == null || value === 0 ? "" : value > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
}

function ResultRow({ row }: { row: ScreenerRow }) {
  return <tr>
    <td><Link href={`/piyasalar/${row.ticker}`} className="font-semibold text-[var(--primary)]">{row.ticker}</Link><p className="mt-0.5 max-w-[220px] truncate text-[10px] text-[var(--text-muted)]" title={row.name ?? undefined}>{row.sector}{row.name ? ` · ${row.name}` : ""}</p></td>
    <td className={`text-right ${tone(row.change_1d_pct)}`}><span className="block text-[var(--text)]">{formatMoney(row.last_price)}</span>{formatPercent(row.change_1d_pct, true)}</td>
    <td className={`text-right ${tone(row.change_1m_pct)}`}>{formatPercent(row.change_1m_pct, true)}</td>
    <td className="text-right">{formatMoney(row.market_cap_try, true)}</td>
    <td className="text-right">{row.composite_score == null ? "—" : <><span className="font-semibold">{formatNumber(row.composite_score, 0)}</span><span className={`ml-1.5 text-[10px] ${row.signal_label?.includes("POSITIVE") ? "text-[var(--positive)]" : row.signal_label?.includes("NEGATIVE") ? "text-[var(--negative)]" : "text-[var(--text-muted)]"}`}>{row.signal_label ? signalName(row.signal_label) : ""}</span></>}</td>
    <td className="text-right">{formatNumber(row.pe_ratio, 1)}</td>
    <td className="text-right">{formatNumber(row.pb_ratio, 2)}</td>
    <td className={`text-right ${tone(row.roe_pct)}`}>{formatPercent(row.roe_pct)}</td>
    <td className={`text-right ${tone(row.revenue_yoy_pct)}`}>{formatPercent(row.revenue_yoy_pct, true)}</td>
    <td className={`text-right ${tone(row.upside_pct)}`}>{formatPercent(row.upside_pct, true)}{row.analyst_count ? <span className="block text-[10px] text-[var(--text-muted)]">{row.analyst_count} kurum</span> : null}</td>
  </tr>;
}
