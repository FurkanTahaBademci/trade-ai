"use client";

import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "trade-ai:watchlist";
const listeners = new Set<() => void>();

function readRaw(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function writeRaw(tickers: string[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
  } catch {
    // localStorage kullanılamıyor (gizli sekme/devre dışı) — sessizce yok say.
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return readRaw().join(",");
}

function getServerSnapshot() {
  return "";
}

/** Kişisel izleme listesi — yalnız bu tarayıcıda saklanır (localStorage), sunucuya gitmez. */
export function useWatchlist() {
  const serialized = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const tickers = serialized ? serialized.split(",") : [];

  const isWatched = useCallback((ticker: string) => tickers.includes(ticker), [tickers]);

  const toggle = useCallback((ticker: string) => {
    const current = readRaw();
    const next = current.includes(ticker) ? current.filter((item) => item !== ticker) : [...current, ticker];
    writeRaw(next);
  }, []);

  return { tickers, isWatched, toggle };
}
