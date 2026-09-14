export type ApiResult<T> = { data: T; ok: true } | { data: T; ok: false; error: string };

function apiBase() { return process.env.API_INTERNAL_URL ?? "http://localhost:8000"; }

export async function apiGet<T>(
  path: string,
  fallback: T,
  options?: { revalidate?: number },
): Promise<ApiResult<T>> {
  try {
    const revalidate = options?.revalidate ?? 30;
    const fetchOptions: RequestInit =
      revalidate === 0
        ? { cache: "no-store" }
        : { next: { revalidate } };

    const response = await fetch(`${apiBase()}${path}`, fetchOptions);
    if (!response.ok) return { data: fallback, ok: false, error: `HTTP ${response.status}` };
    return { data: (await response.json()) as T, ok: true };
  } catch (error) {
    return { data: fallback, ok: false, error: error instanceof Error ? error.message : "Servise ulaşılamadı" };
  }
}

