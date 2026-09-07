export type ApiResult<T> = { data: T; ok: true } | { data: T; ok: false; error: string };

function apiBase() { return process.env.API_INTERNAL_URL ?? "http://localhost:8000"; }

export async function apiGet<T>(path: string, fallback: T): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
    if (!response.ok) return { data: fallback, ok: false, error: `HTTP ${response.status}` };
    return { data: (await response.json()) as T, ok: true };
  } catch (error) {
    return { data: fallback, ok: false, error: error instanceof Error ? error.message : "Servise ulaşılamadı" };
  }
}
