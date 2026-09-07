"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Instrument } from "@/lib/types";
import { Icon } from "./icon";
import { EmptyState } from "./ui";
import { Pagination } from "./pagination";

export function InstrumentList({ instruments }: { instruments: Instrument[] }) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const filtered = useMemo(() => { const value = query.trim().toLocaleUpperCase("tr-TR"); return instruments.filter((item) => !value || item.ticker.includes(value) || item.name.toLocaleUpperCase("tr-TR").includes(value)); }, [instruments, query]);
  const pageSize = 20; const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize)); const safePage = Math.min(page, pageCount); const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);
  return <>
    <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><label className="relative block w-full max-w-md"><Icon name="search" size={16} className="absolute left-3 top-3 text-[var(--text-muted)]"/><input className="input pl-9" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Kod veya şirket adıyla ara" aria-label="Hisse ara"/></label><p className="text-xs text-[var(--text-muted)]">{filtered.length} hisse gösteriliyor</p></div>
    {filtered.length ? <><div className="table-shell overflow-x-auto"><table className="data-table min-w-[680px]"><thead><tr><th>Hisse</th><th>Şirket</th><th>Merkez</th><th>Durum</th><th className="w-10"></th></tr></thead><tbody>{visible.map((item) => <tr key={item.ticker}><td><Link href={`/piyasalar/${item.ticker}`} className="font-semibold text-[var(--primary)]">{item.ticker}</Link></td><td className="font-medium">{item.name}</td><td className="text-[var(--text-secondary)]">{item.city || "—"}</td><td><span className="pill pill-positive"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>Aktif</span></td><td><Link href={`/piyasalar/${item.ticker}`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td></tr>)}</tbody></table></div><Pagination page={safePage} pageCount={pageCount} onChange={setPage}/></> : <div className="panel-flat"><EmptyState title="Hisse bulunamadı" description="Arama ifadenizi değiştirerek tekrar deneyin."/></div>}
  </>;
}
