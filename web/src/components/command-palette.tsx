"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { MarketFeedItem } from "@/lib/types";
import { Icon } from "./icon";

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [items, setItems] = useState<MarketFeedItem[] | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setIndex(0);
    inputRef.current?.focus();
    if (items == null) {
      fetch("/api/market-feed", { cache: "no-store" })
        .then((response) => (response.ok ? response.json() : []))
        .then((data: MarketFeedItem[]) => setItems(Array.isArray(data) ? data : []))
        .catch(() => setItems([]));
    }
  }, [open, items]);

  const results = useMemo(() => {
    const value = query.trim().toLocaleUpperCase("tr-TR");
    if (!items) return [];
    const filtered = !value
      ? items
      : items.filter((item) => item.ticker.includes(value) || item.name.toLocaleUpperCase("tr-TR").includes(value));
    return filtered
      .sort((a, b) => Number(b.ticker.startsWith(value)) - Number(a.ticker.startsWith(value)))
      .slice(0, 8);
  }, [items, query]);

  function select(item: MarketFeedItem) {
    setOpen(false);
    router.push(`/piyasalar/${item.ticker}`);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") { event.preventDefault(); setIndex((i) => Math.min(i + 1, results.length - 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
    else if (event.key === "Enter" && results[index]) { event.preventDefault(); select(results[index]); }
  }

  return <>
    <button type="button" onClick={() => setOpen(true)} className="hidden h-9 w-56 items-center gap-2 rounded-[10px] border px-3 text-xs text-[var(--text-muted)] transition hover:bg-[var(--surface-hover)] md:flex" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <Icon name="search" size={15}/> Hisse ara... <kbd className="ml-auto text-[10px]">⌘ K</kbd>
    </button>
    {open && <div className="fixed inset-0 z-[60] grid place-items-start justify-center pt-[12vh]">
      <button type="button" aria-label="Kapat" className="fixed inset-0 bg-[var(--overlay)]" onClick={() => setOpen(false)}/>
      <div role="dialog" aria-modal="true" aria-label="Hisse arama" className="relative w-[min(560px,92vw)] overflow-hidden rounded-[14px] border shadow-2xl" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>
        <div className="flex items-center gap-2 border-b px-4" style={{ borderColor: "var(--border)" }}>
          <Icon name="search" size={16} className="text-[var(--text-muted)]"/>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setIndex(0); }}
            onKeyDown={onKeyDown}
            placeholder="Kod veya şirket adıyla ara..."
            aria-label="Hisse ara"
            className="h-14 w-full bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]"
          />
          <kbd className="text-[10px] text-[var(--text-muted)]">Esc</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {items == null ? <p className="p-4 text-center text-xs text-[var(--text-muted)]">Yükleniyor...</p>
            : results.length === 0 ? <p className="p-4 text-center text-xs text-[var(--text-muted)]">{query ? "Eşleşen hisse yok" : "Aramaya başlayın"}</p>
            : results.map((item, i) => <button key={item.ticker} type="button" onMouseEnter={() => setIndex(i)} onClick={() => select(item)} className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left text-sm transition ${i === index ? "bg-[var(--primary-soft)] text-[var(--primary)]" : "hover:bg-[var(--surface-hover)]"}`}>
              <span className="font-semibold">{item.ticker}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-muted)]">{item.name}</span>
              {item.composite_score != null && <span className="text-[10px] text-[var(--text-muted)]">{Math.round(item.composite_score)}/100</span>}
            </button>)}
        </div>
      </div>
    </div>}
  </>;
}
