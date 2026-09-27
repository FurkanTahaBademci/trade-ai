"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { MarketFeedItem } from "@/lib/types";
import { fetchMarketFeed, searchMarketFeed } from "@/lib/market-feed";
import { Icon } from "./icon";

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [items, setItems] = useState<MarketFeedItem[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadItems = useCallback(() => {
    setItems(null);
    setLoadError(false);
    fetchMarketFeed()
      .then(setItems)
      .catch(() => {
        setItems([]);
        setLoadError(true);
      });
  }, []);

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
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    inputRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    if (open && items == null) loadItems();
  }, [items, loadItems, open]);

  const results = useMemo(() => searchMarketFeed(items ?? [], query), [items, query]);

  function select(item: MarketFeedItem) {
    setOpen(false);
    router.push(`/piyasalar/${item.ticker}`);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && results.length) { event.preventDefault(); setIndex((i) => Math.min(i + 1, results.length - 1)); }
    else if (event.key === "ArrowUp" && results.length) { event.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
    else if (event.key === "Enter" && results[index]) { event.preventDefault(); select(results[index]); }
  }

  return <>
    <button type="button" onClick={() => setOpen(true)} aria-label="Hisse ara" className="flex h-9 w-9 items-center justify-center gap-2 rounded border text-xs text-[var(--text-muted)] transition hover:bg-[var(--surface-hover)] md:w-56 md:justify-start md:px-3" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <Icon name="search" size={15}/><span className="hidden md:inline">Hisse ara...</span><kbd className="ml-auto hidden text-[10px] md:inline">Ctrl K</kbd>
    </button>
    {open && <div className="fixed inset-0 z-[60] grid place-items-start justify-center pt-[12vh]">
      <button type="button" aria-label="Kapat" className="fixed inset-0 bg-[var(--overlay)]" onClick={() => setOpen(false)}/>
      <div role="dialog" aria-modal="true" aria-label="Hisse arama" className="relative w-[min(560px,92vw)] overflow-hidden rounded border shadow-2xl" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>
        <div className="flex items-center gap-2 border-b px-4" style={{ borderColor: "var(--border)" }}>
          <Icon name="search" size={16} className="text-[var(--text-muted)]"/>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setIndex(0); }}
            onKeyDown={onKeyDown}
            placeholder="Kod veya şirket adıyla ara..."
            aria-label="Hisse ara"
            aria-controls="market-search-results"
            aria-expanded="true"
            aria-activedescendant={results[index] ? `market-result-${results[index].ticker}` : undefined}
            role="combobox"
            className="h-14 w-full bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]"
          />
          <kbd className="text-[10px] text-[var(--text-muted)]">Esc</kbd>
        </div>
        <div id="market-search-results" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {items == null ? <p className="p-4 text-center text-xs text-[var(--text-muted)]">Yükleniyor...</p>
            : loadError ? <div className="p-4 text-center"><p className="text-xs text-[var(--negative)]">Piyasa verileri yüklenemedi.</p><button type="button" onClick={loadItems} className="mt-3 rounded-md border px-3 py-1.5 text-xs" style={{ borderColor: "var(--border)" }}>Tekrar dene</button></div>
            : results.length === 0 ? <p className="p-4 text-center text-xs text-[var(--text-muted)]">{query ? "Eşleşen hisse yok" : "Aramaya başlayın"}</p>
            : results.map((item, i) => <button id={`market-result-${item.ticker}`} role="option" aria-selected={i === index} key={item.ticker} type="button" onMouseEnter={() => setIndex(i)} onClick={() => select(item)} className={`flex w-full items-center gap-3 rounded px-3 py-2.5 text-left text-sm transition ${i === index ? "bg-[var(--primary-soft)] text-[var(--primary)]" : "hover:bg-[var(--surface-hover)]"}`}>
              <span className="font-semibold">{item.ticker}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-muted)]">{item.name}</span>
              {item.composite_score != null && <span className="text-[10px] text-[var(--text-muted)]">{Math.round(item.composite_score)}/100</span>}
            </button>)}
        </div>
      </div>
    </div>}
  </>;
}
