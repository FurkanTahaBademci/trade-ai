/**
 * Yönetim girişi için kaba kuvvet koruması (süreç belleğinde; tek web
 * container'ı için yeterli). İstemci başına 5, toplamda 30 hatalı deneme
 * 15 dakikalık pencerede kilit oluşturur. Toplam sınır, X-Forwarded-For
 * başlığını değiştirerek istemci sınırını aşmaya çalışan saldırgana karşıdır.
 */

export const LOGIN_WINDOW_MS = 15 * 60 * 1000;
export const LOGIN_MAX_FAILURES_PER_CLIENT = 5;
export const LOGIN_MAX_FAILURES_GLOBAL = 30;

const GLOBAL_KEY = "*";

export type FailureStore = Map<string, number[]>;

function recent(store: FailureStore, key: string, nowMs: number): number[] {
  const kept = (store.get(key) ?? []).filter((time) => nowMs - time < LOGIN_WINDOW_MS);
  if (kept.length) store.set(key, kept);
  else store.delete(key);
  return kept;
}

/** Kilitliyse kalan süreyi (ms), değilse 0 döndürür. */
export function lockoutRemainingMs(store: FailureStore, client: string, nowMs: number = Date.now()): number {
  const checks: [string, number][] = [[client, LOGIN_MAX_FAILURES_PER_CLIENT], [GLOBAL_KEY, LOGIN_MAX_FAILURES_GLOBAL]];
  let remaining = 0;
  for (const [key, limit] of checks) {
    const failures = recent(store, key, nowMs);
    if (failures.length >= limit) {
      remaining = Math.max(remaining, failures[failures.length - limit] + LOGIN_WINDOW_MS - nowMs);
    }
  }
  return remaining;
}

export function recordFailure(store: FailureStore, client: string, nowMs: number = Date.now()): void {
  for (const key of [client, GLOBAL_KEY]) {
    store.set(key, [...recent(store, key, nowMs), nowMs]);
  }
}

export function clearFailures(store: FailureStore, client: string): void {
  store.delete(client);
}
