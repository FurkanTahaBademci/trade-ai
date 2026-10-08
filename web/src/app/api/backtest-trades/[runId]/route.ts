import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  if (!/^[1-9]\d{0,15}$/.test(runId)) return NextResponse.json({ detail: "Geçersiz koşu." }, { status: 400 });
  const incoming = request.nextUrl.searchParams;
  const requested = Number(incoming.get("limit") ?? 25);
  const outgoing = new URLSearchParams({ limit: String(Number.isInteger(requested) ? Math.min(25, Math.max(1, requested)) : 25) });
  for (const name of ["ticker", "side", "before_id"]) {
    const value = incoming.get(name);
    if (value) outgoing.set(name, value);
  }
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/backtests/${runId}/trades?${outgoing}`, {
      cache: "no-store", signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) return NextResponse.json({ detail: "İşlemler alınamadı." }, { status: response.status });
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}
