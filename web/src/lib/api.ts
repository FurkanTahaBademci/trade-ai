export type ApiResult<T> = { data: T; ok: true } | { data: T; ok: false; error: string };

function apiBase() { return process.env.API_INTERNAL_URL ?? "http://localhost:8000"; }

export async function apiGet<T>(
  path: string,
  fallback: T,
  options?: { revalidate?: number },
): Promise<ApiResult<T>> {
  const revalidate = options?.revalidate ?? 0;
  const fetchOptions: RequestInit =
    revalidate === 0
      ? { cache: "no-store" }
      : { next: { revalidate } };

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
        return { data: fallback, ok: false, error: `HTTP ${response.status}` };
      }
      return { data: (await response.json()) as T, ok: true };
    } catch (error) {
      if (attempt === 1) {
        await new Promise((r) => setTimeout(r, 200));
        continue;
      }
      return { data: fallback, ok: false, error: error instanceof Error ? error.message : "Servise ulaşılamadı" };
    }
  }
  return { data: fallback, ok: false, error: "Servise ulaşılamadı" };
}


