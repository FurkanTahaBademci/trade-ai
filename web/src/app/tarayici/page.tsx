import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { ScreenerResult } from "@/lib/types";
import { formatDate, formatNumber } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice } from "@/components/ui";
import { Icon } from "@/components/icon";
import { ScreenerTable } from "@/components/screener-table";
import { ScreenerFilters } from "@/components/screener-filters";
import { MARKET_CAP_OPTIONS, SCREENER_MAX_ROWS, SCREENER_PRESETS, SIGNAL_GROUPS, TABLE_COLUMNS, activeFilterCount, moreHref, parseScreenerParams, screenerApiQuery, screenerHref, sortHref, toTableRow, type ScreenerParams } from "@/lib/screener";

export const metadata: Metadata = {
  title: "Hisse Tarayıcı",
  description: "BIST hisselerini bileşik skor, F/K, PD/DD, kârlılık, büyüme, momentum ve analist potansiyeline göre filtreleyin.",
};

export default async function ScreenerPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = parseScreenerParams(await searchParams);
  const result = await apiGet<ScreenerResult | null>(`/api/markets/screener?${screenerApiQuery(params)}`, null, { revalidate: 60 });
  const data = result.data;
  const more = data ? moreHref(params, data.matched) : null;
  const filterCount = activeFilterCount(params);
  return <>
    <PageHeader eyebrow="BIST · Çok kriterli filtre" title="Hisse Tarayıcı" description="Bileşik skor, değerleme, kârlılık, büyüme, momentum ve analist potansiyeline göre tüm BIST evrenini tarayın. Her tarama adres çubuğundan paylaşılabilir." actions={<a href={`/api/export/screener?${screenerApiQuery(params, SCREENER_MAX_ROWS)}`} download className="pill transition hover:text-[var(--text)]"><Icon name="download" size={12}/>CSV indir</a>}/>
    <ServiceNotice show={!result.ok}/>
    <nav aria-label="Hazır taramalar" className="mb-4 flex flex-wrap gap-2">{SCREENER_PRESETS.map((preset) => { const href = screenerHref(preset.params); const active = href === screenerHref(params); return <Link key={preset.label} href={href} title={preset.description} aria-current={active ? "page" : undefined} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{preset.label}</Link>; })}</nav>
    <ScreenerFilters activeCount={filterCount}><form action="/tarayici" method="get" className="panel-flat grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
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
    </form></ScreenerFilters>
    {data && <p className="mb-3 text-xs text-[var(--text-muted)]" role="status"><strong className="text-[var(--text)]">{formatNumber(data.matched, 0)}</strong> / {formatNumber(data.total, 0)} hisse eşleşti{data.as_of_date ? ` · fiyatlar ${formatDate(data.as_of_date)}` : ""}{data.matched > data.rows.length ? ` · ilk ${data.rows.length} gösteriliyor` : ""}</p>}
    {data?.rows.length ? <><ScreenerTable rows={data.rows.map(toTableRow)} headers={TABLE_COLUMNS.map((column) => ({ ...column, href: sortHref(params, column.key), sort: params.sort === column.key ? params.order : null }))}/>{more && <div className="mt-3 flex justify-center"><Link href={more} scroll={false} className="pill transition hover:text-[var(--text)]">Daha fazla göster ({formatNumber(data.matched - data.rows.length, 0)} hisse daha)</Link></div>}</>
      : <div className="panel-flat"><EmptyState title={result.ok ? "Eşleşen hisse yok" : "Tarama sonuçları alınamadı"} description={result.ok ? "Filtreleri gevşetin veya hazır taramalardan birini deneyin. Değeri bilinmeyen hisseler o kritere uymuş sayılmaz." : "Veri servisine ulaşılamadı; biraz sonra tekrar deneyin."}/></div>}
    <p className="mt-4 text-xs leading-5 text-[var(--text-muted)]">F/K son 12 ay net kârıyla, PD/DD son bilançodaki özsermayeyle hesaplanır; zarar eden veya özsermayesi negatif şirketlerde gösterilmez; "—" değerin hesaplanamadığını belirtir (üzerine gelince nedeni görünür). Gelir büyümesi ve ROE son açıklanan döneme aittir. Bir kritere filtre verildiğinde o değeri bilinmeyen hisseler listeden çıkar. Tarama sonuçları bilgi amaçlıdır; yatırım tavsiyesi değildir.</p>
  </>;
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  // Uzun etiketler iki satıra kaysa da kutular aynı hizada kalsın.
  return <label className={`flex min-w-0 flex-col justify-end ${className}`}><span className="eyebrow mb-1.5 block">{label}</span>{children}</label>;
}

function NumberField({ params, name, label, placeholder }: { params: ScreenerParams; name: keyof ScreenerParams; label: string; placeholder?: string }) {
  return <Field label={label}><input name={name} defaultValue={params[name] ?? ""} inputMode="decimal" className="input" placeholder={placeholder} autoComplete="off"/></Field>;
}

