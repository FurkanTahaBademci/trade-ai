import { NextRequest, NextResponse } from "next/server";
import { accountRequest, sessionToken } from "@/lib/account-server";

// Kullanıcının kendi koşusunun işlemleri (sayfalı); başkasının koşusu API'de 404 döner.
export async function GET(request: NextRequest, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  if (!/^[1-9]\d{0,15}$/.test(runId)) return NextResponse.json({ detail: "Geçersiz koşu." }, { status: 400 });
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "Giriş gerekli." }, { status: 401 });
  const incoming = request.nextUrl.searchParams;
  const requested = Number(incoming.get("limit") ?? 25);
  const outgoing = new URLSearchParams({ limit: String(Number.isInteger(requested) ? Math.min(25, Math.max(1, requested)) : 25) });
  for (const name of ["ticker", "side", "before_id"]) {
    const value = incoming.get(name);
    if (value) outgoing.set(name, value);
  }
  const result = await accountRequest(`/api/me/backtests/${runId}/trades?${outgoing}`, token);
  if (!result.ok) return NextResponse.json({ detail: result.message }, { status: result.status });
  return NextResponse.json(result.data, { headers: { "Cache-Control": "private, no-store" } });
}
