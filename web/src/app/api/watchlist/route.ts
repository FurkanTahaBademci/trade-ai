import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, adminAuthState } from "@/lib/admin-auth";
import { normalizeWatchlist } from "@/lib/watchlist-data";

// Yönetici girişliyken izleme listesi sunucuyla senkron tutulur; bildirimler bu
// listeyi izler. Ziyaretçiler 401 alır ve liste yalnız tarayıcılarında kalır.

function authorized(request: NextRequest): boolean {
  const state = adminAuthState(request.cookies.get(ADMIN_SESSION_COOKIE)?.value);
  return state === "authorized" || state === "disabled";
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  return !origin || origin === request.nextUrl.origin;
}

async function forward(init: RequestInit): Promise<NextResponse> {
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/watchlist`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
      headers: { "Content-Type": "application/json", "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "" },
    });
    if (!response.ok) return NextResponse.json({ detail: "İzleme listesi senkronlanamadı." }, { status: response.status });
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}

export async function GET(request: NextRequest) {
  if (!authorized(request)) return NextResponse.json({ detail: "Yönetici girişi gerekli." }, { status: 401 });
  return forward({ method: "GET" });
}

export async function PUT(request: NextRequest) {
  if (!authorized(request)) return NextResponse.json({ detail: "Yönetici girişi gerekli." }, { status: 401 });
  if (!sameOrigin(request)) return NextResponse.json({ detail: "Geçersiz istek kaynağı." }, { status: 403 });
  const body = (await request.json().catch(() => null)) as { tickers?: unknown } | null;
  const tickers = normalizeWatchlist(body?.tickers).slice(0, 200);
  return forward({ method: "PUT", body: JSON.stringify({ tickers }) });
}
