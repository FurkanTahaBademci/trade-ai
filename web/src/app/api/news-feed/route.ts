import { NextRequest, NextResponse } from "next/server";

const MAX_PAGE_SIZE = 24;

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

export async function GET(request: NextRequest) {
  const incoming = request.nextUrl.searchParams;
  const requestedLimit = Number(incoming.get("limit") ?? 12);
  const limit = Number.isInteger(requestedLimit)
    ? Math.min(Math.max(requestedLimit, 1), MAX_PAGE_SIZE)
    : 12;
  const params = new URLSearchParams({ limit: String(limit) });

  for (const name of ["source", "before", "before_id"] as const) {
    const value = incoming.get(name);
    if (value) params.set(name, value);
  }

  try {
    const response = await fetch(`${apiBase()}/api/news?${params}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) {
      return NextResponse.json({ detail: "Haber servisi yanıt vermedi." }, { status: response.status });
    }
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ detail: "Haber servisine ulaşılamadı." }, { status: 503 });
  }
}
