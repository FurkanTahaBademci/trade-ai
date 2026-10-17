"use client";

import Link from "next/link";
import { formatMoney, formatNumber, formatPercent, signalName } from "@/lib/format";
import type { ScreenerSort, TableRow } from "@/lib/screener";

// Tablo istemci bileşeni: sunucu bileşeni olarak render edildiğinde her hücrenin
// sınıf adları hem HTML'de hem RSC verisinde tekrar ediyordu. Burada yalnız
// gösterilen alanlar prop olarak gider. Kolonlar ve satır dönüşümü sunucuda da
// çalıştığı için `@/lib/screener` içindedir ("use client" modülündeki değerler
// sunucu bileşeninden çağrılamaz).

type Header = { key: ScreenerSort; label: string; title?: string; href: string; sort: "asc" | "desc" | null };

// "—" tek başına neden boş olduğunu söylemiyordu; üzerine gelince gerekçe görünür.
const MISSING: Partial<Record<ScreenerSort, string>> = {
  pe_ratio: "Hesaplanamadı: şirket son 12 ayda zarar etmiş ya da kâr verisi eksik",
  pb_ratio: "Hesaplanamadı: özsermaye negatif ya da son bilançoda özsermaye verisi yok",
  roe_pct: "Hesaplanamadı: son dönemde kâr veya özsermaye verisi yok",
  revenue_yoy_pct: "Hesaplanamadı: karşılaştırılabilir önceki yıl geliri yok",
  upside_pct: "Kurum hedef fiyatı bulunmuyor",
  change_1m_pct: "Yeterli fiyat geçmişi yok",
  market_cap_try: "Piyasa değeri verisi yok",
  composite_score: "Bileşik skor henüz hesaplanmadı",
};

function Missing({ field }: { field: ScreenerSort }) {
  const reason = MISSING[field] ?? "Veri yok";
  return <span className="relative cursor-help text-[var(--text-muted)]" title={reason}><span aria-hidden="true">—</span><span className="sr-only">{reason}</span></span>;
}

function orMissing(value: number | null, field: ScreenerSort, text: string) {
  return value == null || !Number.isFinite(value) ? <Missing field={field}/> : text;
}

export function ScreenerTable({ rows, headers }: { rows: TableRow[]; headers: Header[] }) {
  return <>
    {/* Mobil: kart görünümü + sıralama çipleri */}
    <div className="md:hidden">
      <nav aria-label="Sıralama" className="no-scrollbar relative -mx-3 mb-3 flex gap-1.5 overflow-x-auto px-3 pb-1">{headers.map((column) => <Link key={column.key} href={column.href} scroll={false} aria-current={column.sort ? "true" : undefined} className={`pill shrink-0 whitespace-nowrap transition ${column.sort ? "pill-primary" : "hover:text-[var(--text)]"}`}>{column.label}{column.sort && <span aria-hidden="true">{column.sort === "asc" ? "↑" : "↓"}</span>}{column.sort && <span className="sr-only">{column.sort === "asc" ? " (artan)" : " (azalan)"}</span>}</Link>)}</nav>
      <ul className="space-y-2">{rows.map((row) => <ResultCard key={row.ticker} row={row}/>)}</ul>
    </div>
    {/* Masaüstü: başlık ve hisse sütunu kaydırırken sabit kalır */}
    <div className="table-shell hidden max-h-[calc(100dvh-7rem)] overflow-auto md:block"><table className="data-table data-table-sticky min-w-[980px]"><caption className="sr-only">Tarama sonuçları</caption><thead><tr>{headers.map((column) => <th key={column.key} scope="col" title={column.title} aria-sort={column.sort === "asc" ? "ascending" : column.sort === "desc" ? "descending" : undefined} className={column.key === "ticker" ? "sticky-col" : "text-right"}><Link href={column.href} scroll={false} className="inline-flex items-center gap-1 hover:text-[var(--text)]">{column.label}{column.sort && <span aria-hidden="true">{column.sort === "asc" ? "↑" : "↓"}</span>}</Link></th>)}</tr></thead><tbody>{rows.map((row) => <ResultRow key={row.ticker} row={row}/>)}</tbody></table></div>
  </>;
}

function tone(value: number | null) {
  return value == null || value === 0 ? "" : value > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
}

function signalTone(label: string | null) {
  return label?.includes("POSITIVE") ? "text-[var(--positive)]" : label?.includes("NEGATIVE") ? "text-[var(--negative)]" : "text-[var(--text-muted)]";
}

function ResultRow({ row }: { row: TableRow }) {
  return <tr>
    <td className="sticky-col"><Link href={`/piyasalar/${row.ticker}`} className="font-semibold text-[var(--primary)]">{row.ticker}</Link><p className="mt-0.5 max-w-[220px] truncate text-xs text-[var(--text-muted)]" title={row.name ?? undefined}>{row.sector}{row.name ? ` · ${row.name}` : ""}</p></td>
    <td className={`text-right ${tone(row.change_1d_pct)}`}><span className="block text-[var(--text)]">{formatMoney(row.last_price)}</span>{formatPercent(row.change_1d_pct, true)}</td>
    <td className={`text-right ${tone(row.change_1m_pct)}`}>{orMissing(row.change_1m_pct, "change_1m_pct", formatPercent(row.change_1m_pct, true))}</td>
    <td className="whitespace-nowrap text-right">{orMissing(row.market_cap_try, "market_cap_try", formatMoney(row.market_cap_try, true))}</td>
    <td className="text-right">{row.composite_score == null ? <Missing field="composite_score"/> : <><span className="font-semibold">{formatNumber(row.composite_score, 0)}</span><span className={`ml-1.5 whitespace-nowrap text-xs ${signalTone(row.signal_label)}`}>{row.signal_label ? signalName(row.signal_label) : ""}</span></>}</td>
    <td className="text-right">{orMissing(row.pe_ratio, "pe_ratio", formatNumber(row.pe_ratio, 1))}</td>
    <td className="text-right">{orMissing(row.pb_ratio, "pb_ratio", formatNumber(row.pb_ratio, 2))}</td>
    <td className={`text-right ${tone(row.roe_pct)}`}>{orMissing(row.roe_pct, "roe_pct", formatPercent(row.roe_pct))}</td>
    <td className={`text-right ${tone(row.revenue_yoy_pct)}`}>{orMissing(row.revenue_yoy_pct, "revenue_yoy_pct", formatPercent(row.revenue_yoy_pct, true))}</td>
    <td className={`text-right ${tone(row.upside_pct)}`}>{orMissing(row.upside_pct, "upside_pct", formatPercent(row.upside_pct, true))}{row.analyst_count ? <span className="block text-xs text-[var(--text-muted)]">{row.analyst_count} kurum</span> : null}</td>
  </tr>;
}

function ResultCard({ row }: { row: TableRow }) {
  return <li className="panel-flat p-3">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="flex items-baseline gap-2"><Link href={`/piyasalar/${row.ticker}`} className="font-semibold text-[var(--primary)]">{row.ticker}</Link><span className="text-xs">{formatMoney(row.last_price)}</span></p>
        <p className="truncate text-xs text-[var(--text-muted)]" title={row.name ?? undefined}>{row.sector}{row.name ? ` · ${row.name}` : ""}</p>
      </div>
      <div className="shrink-0 text-right">
        {row.composite_score == null ? <Missing field="composite_score"/> : <><span className="text-lg font-semibold leading-none">{formatNumber(row.composite_score, 0)}</span><span className={`block text-xs ${signalTone(row.signal_label)}`}>{row.signal_label ? signalName(row.signal_label) : "Skor"}</span></>}
      </div>
    </div>
    <dl className="mt-2.5 grid grid-cols-4 gap-x-2 gap-y-2 border-t pt-2.5 text-xs" style={{ borderColor: "var(--border)" }}>
      <CardStat label="Gün" className={tone(row.change_1d_pct)}>{formatPercent(row.change_1d_pct, true)}</CardStat>
      <CardStat label="F/K">{orMissing(row.pe_ratio, "pe_ratio", formatNumber(row.pe_ratio, 1))}</CardStat>
      <CardStat label="PD/DD">{orMissing(row.pb_ratio, "pb_ratio", formatNumber(row.pb_ratio, 2))}</CardStat>
      <CardStat label="ROE" className={tone(row.roe_pct)}>{orMissing(row.roe_pct, "roe_pct", formatPercent(row.roe_pct))}</CardStat>
      <CardStat label="1 ay" className={tone(row.change_1m_pct)}>{orMissing(row.change_1m_pct, "change_1m_pct", formatPercent(row.change_1m_pct, true))}</CardStat>
      <CardStat label="Piy. değ.">{orMissing(row.market_cap_try, "market_cap_try", formatMoney(row.market_cap_try, true))}</CardStat>
      <CardStat label="Gelir büy." className={tone(row.revenue_yoy_pct)}>{orMissing(row.revenue_yoy_pct, "revenue_yoy_pct", formatPercent(row.revenue_yoy_pct, true))}</CardStat>
      <CardStat label="Analist pot." className={tone(row.upside_pct)}><span title={row.analyst_count ? `${row.analyst_count} kurum` : undefined}>{orMissing(row.upside_pct, "upside_pct", formatPercent(row.upside_pct, true))}</span></CardStat>
    </dl>
  </li>;
}

function CardStat({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return <div className={`min-w-0 ${className}`}><dt className="text-[var(--text-muted)]">{label}</dt><dd className="mt-0.5 truncate font-medium">{children}</dd></div>;
}
