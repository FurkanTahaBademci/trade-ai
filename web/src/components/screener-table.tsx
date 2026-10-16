"use client";

import Link from "next/link";
import { formatMoney, formatNumber, formatPercent, signalName } from "@/lib/format";
import type { ScreenerSort } from "@/lib/screener";
import type { ScreenerRow } from "@/lib/types";

// Tablo istemci bileşeni: sunucu bileşeni olarak render edildiğinde her hücrenin
// sınıf adları hem HTML'de hem RSC verisinde tekrar ediyordu. Burada yalnız
// gösterilen alanlar prop olarak gider.
export const TABLE_COLUMNS: { key: ScreenerSort; label: string; title?: string }[] = [
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

export type TableRow = Pick<ScreenerRow, "ticker" | "name" | "sector" | "last_price" | "change_1d_pct" | "change_1m_pct" | "market_cap_try" | "composite_score" | "signal_label" | "pe_ratio" | "pb_ratio" | "roe_pct" | "revenue_yoy_pct" | "upside_pct" | "analyst_count">;

export function toTableRow(row: ScreenerRow): TableRow {
  const { ticker, name, sector, last_price, change_1d_pct, change_1m_pct, market_cap_try, composite_score, signal_label, pe_ratio, pb_ratio, roe_pct, revenue_yoy_pct, upside_pct, analyst_count } = row;
  return { ticker, name, sector, last_price, change_1d_pct, change_1m_pct, market_cap_try, composite_score, signal_label, pe_ratio, pb_ratio, roe_pct, revenue_yoy_pct, upside_pct, analyst_count };
}

type Header = { key: ScreenerSort; label: string; title?: string; href: string; sort: "asc" | "desc" | null };

export function ScreenerTable({ rows, headers }: { rows: TableRow[]; headers: Header[] }) {
  return <div className="table-shell overflow-x-auto"><table className="data-table min-w-[980px]"><caption className="sr-only">Tarama sonuçları</caption><thead><tr>{headers.map((column) => <th key={column.key} scope="col" title={column.title} aria-sort={column.sort === "asc" ? "ascending" : column.sort === "desc" ? "descending" : undefined} className={column.key === "ticker" ? "" : "text-right"}><Link href={column.href} scroll={false} className="inline-flex items-center gap-1 hover:text-[var(--text)]">{column.label}{column.sort && <span aria-hidden="true">{column.sort === "asc" ? "↑" : "↓"}</span>}</Link></th>)}</tr></thead><tbody>{rows.map((row) => <ResultRow key={row.ticker} row={row}/>)}</tbody></table></div>;
}

function tone(value: number | null) {
  return value == null || value === 0 ? "" : value > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
}

function ResultRow({ row }: { row: TableRow }) {
  return <tr>
    <td><Link href={`/piyasalar/${row.ticker}`} className="font-semibold text-[var(--primary)]">{row.ticker}</Link><p className="mt-0.5 max-w-[220px] truncate text-[10px] text-[var(--text-muted)]" title={row.name ?? undefined}>{row.sector}{row.name ? ` · ${row.name}` : ""}</p></td>
    <td className={`text-right ${tone(row.change_1d_pct)}`}><span className="block text-[var(--text)]">{formatMoney(row.last_price)}</span>{formatPercent(row.change_1d_pct, true)}</td>
    <td className={`text-right ${tone(row.change_1m_pct)}`}>{formatPercent(row.change_1m_pct, true)}</td>
    <td className="text-right">{formatMoney(row.market_cap_try, true)}</td>
    <td className="text-right">{row.composite_score == null ? "—" : <><span className="font-semibold">{formatNumber(row.composite_score, 0)}</span><span className={`ml-1.5 whitespace-nowrap text-[10px] ${row.signal_label?.includes("POSITIVE") ? "text-[var(--positive)]" : row.signal_label?.includes("NEGATIVE") ? "text-[var(--negative)]" : "text-[var(--text-muted)]"}`}>{row.signal_label ? signalName(row.signal_label) : ""}</span></>}</td>
    <td className="text-right">{formatNumber(row.pe_ratio, 1)}</td>
    <td className="text-right">{formatNumber(row.pb_ratio, 2)}</td>
    <td className={`text-right ${tone(row.roe_pct)}`}>{formatPercent(row.roe_pct)}</td>
    <td className={`text-right ${tone(row.revenue_yoy_pct)}`}>{formatPercent(row.revenue_yoy_pct, true)}</td>
    <td className={`text-right ${tone(row.upside_pct)}`}>{formatPercent(row.upside_pct, true)}{row.analyst_count ? <span className="block text-[10px] text-[var(--text-muted)]">{row.analyst_count} kurum</span> : null}</td>
  </tr>;
}
