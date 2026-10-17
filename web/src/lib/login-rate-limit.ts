/**
 * Yönetim girişi için kaba kuvvet koruması (süreç belleğinde; tek web
 * container'ı için yeterli). İstemci başına 5, toplamda 30 hatalı deneme
 * 15 dakikalık pencerede kilit oluşturur. Toplam sınır, X-Forwarded-For
 * başlığını değiştirerek istemci sınırını aşmaya çalışan saldırgana karşıdır.
 *
 * Web birden fazla süreçle çalışınca (WEB_WORKERS) her süreç ayrı sayar ve
 * istekler süreçlere sırayla dağılır; sınırlar süreç sayısına bölünür ki
 * toplam deneme hakkı tek süreçteki kadar kalsın.
 */

export const LOGIN_WINDOW_MS = 15 * 60 * 1000;
export const LOGIN_MAX_FAILURES_PER_CLIENT = 5;
export const LOGIN_MAX_FAILURES_GLOBAL = 30;

const GLOBAL_KEY = "*";

/** Süreç başına sınır: toplam sınır süreç sayısına bölünür (en az 1). */
export function perProcessLimit(limit: number, processes: number = 1): number {
  const count = Number.isInteger(processes) && processes > 1 ? processes : 1;
  return Math.max(1, Math.ceil(limit / count));
}

export type FailureStore = Map<string, number[]>;

function recent(store: FailureStore, key: string, nowMs: number): number[] {
  const kept = (store.get(key) ?? []).filter((time) => nowMs - time < LOGIN_WINDOW_MS);
  if (kept.length) store.set(key, kept);
  else store.delete(key);
  return kept;
}

/** Kilitliyse kalan süreyi (ms), değilse 0 döndürür. */
export function lockoutRemainingMs(
  store: FailureStore,
  client: string,
  nowMs: number = Date.now(),
  processes: number = 1,
): number {
  const checks: [string, number][] = [
    [client, perProcessLimit(LOGIN_MAX_FAILURES_PER_CLIENT, processes)],
    [GLOBAL_KEY, perProcessLimit(LOGIN_MAX_FAILURES_GLOBAL, processes)],
  ];
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
