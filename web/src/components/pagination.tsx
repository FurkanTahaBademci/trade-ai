"use client";

import { useEffect, useState } from "react";
import { Icon } from "./icon";

export function PaginatedItems({ items, pageSize = 12, className = "space-y-3" }: { items: React.ReactNode[]; pageSize?: number; className?: string }) {
  const [page, setPage] = useState(1); const pageCount = Math.max(1, Math.ceil(items.length / pageSize)); const safePage = Math.min(page, pageCount);
  useEffect(() => { if (page > pageCount) setPage(pageCount); }, [page, pageCount]);
  const start = (safePage - 1) * pageSize;
  return <><div className={className}>{items.slice(start, start + pageSize)}</div>{pageCount > 1 && <Pagination page={safePage} pageCount={pageCount} onChange={setPage}/>}</>;
}

export function Pagination({ page, pageCount, onChange }: { page: number; pageCount: number; onChange: (page: number) => void }) {
  return <nav className="mt-5 flex items-center justify-between gap-3" aria-label="Sayfalama"><p className="text-xs text-[var(--text-muted)]">Sayfa {page} / {pageCount}</p><div className="flex gap-2"><button className="icon-button disabled:cursor-not-allowed disabled:opacity-35" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Önceki sayfa"><Icon name="arrow" size={15} className="rotate-180"/></button><button className="icon-button disabled:cursor-not-allowed disabled:opacity-35" disabled={page >= pageCount} onClick={() => onChange(page + 1)} aria-label="Sonraki sayfa"><Icon name="arrow" size={15}/></button></div></nav>;
}
