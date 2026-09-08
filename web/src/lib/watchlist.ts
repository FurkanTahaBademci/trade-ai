"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { normalizeWatchlist, WATCHLIST_STORAGE_KEY } from "./watchlist-data";

const listeners = new Set<() => void>();

function readRaw(): string[] {
  try {
    const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return normalizeWatchlist(parsed);
  } catch {
    return [];
  }
}

function writeRaw(tickers: string[]) {
  try {
    window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(tickers));
  } catch {
    // localStorage kullanılamıyor (gizli sekme/devre dışı) — sessizce yok say.
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === WATCHLIST_STORAGE_KEY || event.key === null) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function getSnapshot() {
  return JSON.stringify(readRaw());
}

function getServerSnapshot() {
  return "[]";
}

/** Kişisel izleme listesi — yalnız bu tarayıcıda saklanır (localStorage), sunucuya gitmez. */
export function useWatchlist() {
  const serialized = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const tickers = useMemo(() => normalizeWatchlist(JSON.parse(serialized)), [serialized]);

  const isWatched = useCallback((ticker: string) => tickers.includes(ticker), [tickers]);

  const toggle = useCallback((ticker: string) => {
    const normalizedTicker = normalizeWatchlist([ticker])[0];
    if (!normalizedTicker) return;
    const current = readRaw();
    const next = current.includes(normalizedTicker)
      ? current.filter((item) => item !== normalizedTicker)
      : [...current, normalizedTicker];
    writeRaw(next);
  }, []);

  return { tickers, isWatched, toggle };
}
