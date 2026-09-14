import { NextRequest, NextResponse } from "next/server";

const MAX_PAGE_SIZE = 30;
const feeds = {
  backtests: { path: "/api/backtests", parameters: ["before_id"] },
  kap: {
    path: "/api/disclosures",
    parameters: ["before", "before_index"],
  },
  analyses: {
    path: "/api/evaluations",
    parameters: ["source_type", "before", "before_id"],
  },
  signals: {
    path: "/api/signals",
    parameters: ["label", "after_score", "after_ticker", "after_id"],
  },
  watchlist: {
    path: "/api/signals",
    parameters: ["ticker", "tickers", "label", "after_score", "after_ticker", "after_id"],
  },
  portfolio: {
    path: "/api/paper/portfolios",
    parameters: ["ticker", "portfolio_id", "status"],
  },
  portfolios: {
    path: "/api/paper/portfolios",
    parameters: ["ticker", "portfolio_id", "status"],
  },
} as const;

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ kind: string }> },
) {
  const { kind } = await params;
  const feed = feeds[kind as keyof typeof feeds];
  if (!feed) return NextResponse.json({ detail: "Akış bulunamadı." }, { status: 404 });

  const incoming = request.nextUrl.searchParams;
  const requestedLimit = Number(incoming.get("limit") ?? 12);
  const limit = Number.isInteger(requestedLimit)
    ? Math.min(Math.max(requestedLimit, 1), MAX_PAGE_SIZE)
    : 12;
  const outgoing = new URLSearchParams({ limit: String(limit) });
  for (const name of feed.parameters) {
    const value = incoming.get(name);
    if (value) outgoing.set(name, value);
  }

  try {
    const response = await fetch(`${apiBase()}${feed.path}?${outgoing}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) {
      return NextResponse.json({ detail: "Veri servisi yanıt vermedi." }, { status: response.status });
    }
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}
