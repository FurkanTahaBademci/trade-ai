"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { normalizeWatchlist, WATCHLIST_STORAGE_KEY } from "./watchlist-data";

const listeners = new Set<() => void>();
const SYNCED_FLAG_KEY = "trade-ai:watchlist-synced";

// "local": ziyaretçi, liste yalnız tarayıcıda. "synced": yönetici girişli,
// liste sunucuyla senkron ve bildirimlere dahil.
type SyncState = "unknown" | "local" | "synced";
let syncState: SyncState = "unknown";
let syncStarted = false;
const syncListeners = new Set<() => void>();

function setSyncState(next: SyncState) {
  syncState = next;
  for (const listener of syncListeners) listener();
}

function pushToServer(tickers: string[]) {
  void fetch("/api/watchlist", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers }),
  }).catch(() => undefined);
}

async function startSync() {
  if (syncStarted) return;
  syncStarted = true;
  try {
    const response = await fetch("/api/watchlist", { cache: "no-store" });
    if (!response.ok) { setSyncState("local"); return; }
    const server = normalizeWatchlist(((await response.json()) as { tickers?: unknown }).tickers);
    let firstSync = true;
    try { firstSync = window.localStorage.getItem(SYNCED_FLAG_KEY) !== "1"; } catch { /* yok say */ }
    if (firstSync) {
      // İlk senkronda bu tarayıcıdaki liste kaybolmasın: birleştir ve sunucuya yaz.
      const merged = normalizeWatchlist([...server, ...readRaw()]);
      writeRaw(merged, false);
      pushToServer(merged);
      try { window.localStorage.setItem(SYNCED_FLAG_KEY, "1"); } catch { /* yok say */ }
    } else {
      writeRaw(server, false);
    }
    setSyncState("synced");
  } catch {
    setSyncState("local");
  }
}

function readRaw(): string[] {
  try {
    const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return normalizeWatchlist(parsed);
  } catch {
    return [];
  }
}

function writeRaw(tickers: string[], sync = true) {
  try {
    window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(tickers));
  } catch {
    // localStorage kullanılamıyor (gizli sekme/devre dışı) — sessizce yok say.
  }
  for (const listener of listeners) listener();
  if (sync && syncState === "synced") pushToServer(tickers);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  void startSync();
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

/**
 * Kişisel izleme listesi. Ziyaretçide yalnız bu tarayıcıda (localStorage) kalır;
 * yönetici girişliyken sunucuyla senkronlanır ve bildirimlere dahil edilir.
 */
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

function subscribeSync(listener: () => void) {
  syncListeners.add(listener);
  return () => { syncListeners.delete(listener); };
}

/** İzleme listesinin sunucuyla senkron olup olmadığı ("unknown" ilk yüklemede). */
export function useWatchlistSyncState(): SyncState {
  return useSyncExternalStore(subscribeSync, () => syncState, () => "unknown" as SyncState);
}
