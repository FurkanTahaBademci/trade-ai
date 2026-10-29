import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, adminAuthState } from "@/lib/admin-auth";
import { SESSION_COOKIE } from "@/lib/account";
import { accountRequest, apiBase, currentAccount } from "@/lib/account-server";
import { normalizeWatchlist } from "@/lib/watchlist-data";

// Hesapla girişliyken liste kullanıcının hesabına (/api/me/watchlist), ortam
// değişkenli yönetici girişindeyse bildirimlerin izlediği ortak listeye
// (/api/watchlist) yazılır. Ziyaretçiler 401 alır; liste tarayıcılarında kalır.
// `owner`, istemcinin "bu hesapla ilk senkron" kararını verdiği kimliktir.

type Target = { kind: "account"; token: string; owner: string } | { kind: "admin"; owner: "admin" } | null;

async function target(request: NextRequest): Promise<Target> {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    const account = await currentAccount();
    if (account) return { kind: "account", token, owner: `user:${account.id}` };
  }
  const state = adminAuthState(request.cookies.get(ADMIN_SESSION_COOKIE)?.value);
  return state === "authorized" || state === "disabled" ? { kind: "admin", owner: "admin" } : null;
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  return !origin || origin === request.nextUrl.origin;
}

function respond(owner: string, result: { ok: boolean; status: number; data?: unknown }) {
  if (!result.ok) return NextResponse.json({ detail: "İzleme listesi senkronlanamadı." }, { status: result.status, headers: { "Cache-Control": "no-store" } });
  const tickers = (result.data as { tickers?: unknown } | undefined)?.tickers;
  return NextResponse.json({ tickers: normalizeWatchlist(tickers), owner }, { headers: { "Cache-Control": "private, no-store" } });
}

async function forwardAdmin(init: RequestInit): Promise<{ ok: boolean; status: number; data?: unknown }> {
  try {
    const response = await fetch(`${apiBase()}/api/watchlist`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
      headers: { "Content-Type": "application/json", "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "" },
    });
    return { ok: response.ok, status: response.status, data: response.ok ? await response.json() : undefined };
  } catch {
    return { ok: false, status: 503 };
  }
}

export async function GET(request: NextRequest) {
  const where = await target(request);
  if (!where) return NextResponse.json({ detail: "Giriş gerekli." }, { status: 401 });
  if (where.kind === "account") return respond(where.owner, await accountRequest("/api/me/watchlist", where.token));
  return respond(where.owner, await forwardAdmin({ method: "GET" }));
}

export async function PUT(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ detail: "Geçersiz istek kaynağı." }, { status: 403 });
  const where = await target(request);
  if (!where) return NextResponse.json({ detail: "Giriş gerekli." }, { status: 401 });
  const body = (await request.json().catch(() => null)) as { tickers?: unknown } | null;
  const tickers = normalizeWatchlist(body?.tickers).slice(0, 200);
  if (where.kind === "account") return respond(where.owner, await accountRequest("/api/me/watchlist", where.token, { method: "PUT", body: { tickers } }));
  return respond(where.owner, await forwardAdmin({ method: "PUT", body: JSON.stringify({ tickers }) }));
}
