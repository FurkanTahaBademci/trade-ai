export type ApiResult<T> =
  | { data: T; ok: true }
  | { data: T; ok: false; error: string; status?: number };

export function isApiNotFound(result: ApiResult<unknown>): boolean {
  return !result.ok && result.status === 404;
}

function apiBase() { return process.env.API_INTERNAL_URL ?? "http://localhost:8000"; }

// Kök layout `force-dynamic` olduğu için Next her fetch'i no-store yapar ve
// `next.revalidate` etkisiz kalır. Bu yüzden `revalidate` verilen istekler süreç
// içinde kısa süre saklanır; eşzamanlı aynı istekler tek fetch'e bağlanır.
type CacheEntry = { expires: number; value: Promise<ApiResult<unknown>> };
const responseCache = new Map<string, CacheEntry>();
const MAX_CACHE_ENTRIES = 500;

export async function apiGet<T>(
  path: string,
  fallback: T,
  options?: { revalidate?: number },
): Promise<ApiResult<T>> {
  const revalidate = options?.revalidate ?? 0;
  if (revalidate <= 0) return fetchApi(path, fallback);
  const now = Date.now();
  const cached = responseCache.get(path);
  if (cached && cached.expires > now) {
    const result = (await cached.value) as ApiResult<T>;
    return result.ok ? result : { ...result, data: fallback };
  }
  const value = fetchApi(path, fallback);
  responseCache.set(path, { expires: now + revalidate * 1000, value });
  pruneCache(now);
  const result = await value;
  // Hatalı yanıt saklanmaz; bir sonraki istek yeniden dener.
  if (!result.ok && responseCache.get(path)?.value === value) responseCache.delete(path);
  return result;
}

function pruneCache(now: number) {
  if (responseCache.size <= MAX_CACHE_ENTRIES) return;
  for (const [key, entry] of responseCache) if (entry.expires <= now) responseCache.delete(key);
  // Map ekleme sırasını korur: hâlâ fazlaysa en eski kayıtlar düşer.
  for (const key of responseCache.keys()) {
    if (responseCache.size <= MAX_CACHE_ENTRIES) break;
    responseCache.delete(key);
  }
}

async function fetchApi<T>(path: string, fallback: T): Promise<ApiResult<T>> {
  const fetchOptions: RequestInit = { cache: "no-store" };

  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const response = await fetch(`${apiBase()}${path}`, {
        ...fetchOptions,
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) {
        if (attempt === 1 && response.status >= 500) {
          await new Promise((r) => setTimeout(r, 200));
          continue;
        }
        return { data: fallback, ok: false, error: `HTTP ${response.status}`, status: response.status };
      }
      return { data: (await response.json()) as T, ok: true };
    } catch (error) {
      // Zaman aşımında yeniden denemek bekleme süresini ikiye katlar (10 sn + 10 sn).
      const timedOut = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
      if (attempt === 1 && !timedOut) {
        await new Promise((r) => setTimeout(r, 200));
        continue;
      }
      return { data: fallback, ok: false, error: error instanceof Error ? error.message : "Servise ulaşılamadı" };
    }
  }
  return { data: fallback, ok: false, error: "Servise ulaşılamadı" };
}

