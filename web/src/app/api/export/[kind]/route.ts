import { NextRequest, NextResponse } from "next/server";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

/** CSV dışa aktarma: API'nin CSV uçlarına izin verilen parametrelerle aktarılan same-origin proxy. */
export async function GET(request: NextRequest, { params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  const incoming = request.nextUrl.searchParams;
  const outgoing = new URLSearchParams();
  let path: string;
  if (kind === "signals") {
    path = "/api/signals/export.csv";
    for (const name of ["label", "min_score", "as_of"]) {
      const value = incoming.get(name);
      if (value) outgoing.set(name, value);
    }
  } else if (kind === "paper-trades") {
    const portfolioId = incoming.get("portfolio_id") ?? "";
    if (!/^[1-9]\d{0,15}$/.test(portfolioId)) return NextResponse.json({ detail: "Geçersiz portföy." }, { status: 400 });
    path = `/api/paper/portfolios/${portfolioId}/trades.csv`;
    const ticker = incoming.get("ticker");
    if (ticker) outgoing.set("ticker", ticker);
  } else {
    return NextResponse.json({ detail: "Dışa aktarma bulunamadı." }, { status: 404 });
  }
  try {
    const response = await fetch(`${apiBase()}${path}?${outgoing}`, { cache: "no-store", signal: AbortSignal.timeout(30_000) });
    if (!response.ok) return NextResponse.json({ detail: "Dışa aktarma alınamadı." }, { status: response.status });
    return new NextResponse(await response.arrayBuffer(), {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": response.headers.get("content-disposition") ?? `attachment; filename="${kind}.csv"`,
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}
