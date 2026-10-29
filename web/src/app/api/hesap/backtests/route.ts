import { NextRequest, NextResponse } from "next/server";
import { accountRequest, sessionToken } from "@/lib/account-server";

// Kullanıcının kendi backtest koşuları (sonsuz kaydırma); oturum token'ı sunucuda iletilir.
export async function GET(request: NextRequest) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "Giriş gerekli." }, { status: 401 });
  const incoming = request.nextUrl.searchParams;
  const requested = Number(incoming.get("limit") ?? 20);
  const outgoing = new URLSearchParams({ limit: String(Number.isInteger(requested) ? Math.min(20, Math.max(1, requested)) : 20) });
  const before = incoming.get("before_id");
  if (before && /^[1-9]\d{0,15}$/.test(before)) outgoing.set("before_id", before);
  const result = await accountRequest(`/api/me/backtests?${outgoing}`, token);
  if (!result.ok) return NextResponse.json({ detail: result.message }, { status: result.status });
  return NextResponse.json(result.data, { headers: { "Cache-Control": "private, no-store" } });
}
