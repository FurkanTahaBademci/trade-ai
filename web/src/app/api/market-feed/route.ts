import { NextResponse } from "next/server";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

type InstrumentRow = { ticker: string; name: string };
type ScreenerRow = { ticker: string; composite_score: number | null; signal_label: string | null; last_price: number | null; change_1d_pct: number | null };
type MergedRow = InstrumentRow & Omit<ScreenerRow, "ticker">;

// Tüm tarayıcı sekmeleri aynı özeti ister; arka uç verisi zaten dakikalar
// mertebesinde değişir.
const CACHE_MS = 60_000;
let cached: { expires: number; rows: MergedRow[] } | null = null;

/** Komut paleti (arama) ve izleme listesinin kullandığı, tarayıcıdan erişilebilir
 * tek istekli birleşik market özeti: hisse evreni + tarayıcı veri setinden son
 * fiyat, günlük değişim ve bileşik skor (tüm evren, düşük skorlular dahil). */
export async function GET() {
  if (cached && cached.expires > Date.now()) return NextResponse.json(cached.rows);
  try {
    const [instrumentsRes, screenerRes] = await Promise.all([
      fetch(`${apiBase()}/api/instruments`, { cache: "no-store", signal: AbortSignal.timeout(15_000) }),
      fetch(`${apiBase()}/api/markets/screener?limit=1000&sort=ticker&order=asc`, { cache: "no-store", signal: AbortSignal.timeout(15_000) }),
    ]);
    if (!instrumentsRes.ok) {
      return NextResponse.json({ detail: "Veri servisi yanıt vermedi." }, { status: instrumentsRes.status });
    }
    const instruments = (await instrumentsRes.json()) as InstrumentRow[];
    const screener = screenerRes.ok ? ((await screenerRes.json()) as { rows?: ScreenerRow[] }).rows ?? [] : [];
    const byTicker = new Map(screener.map((row) => [row.ticker, row]));

    const rows = instruments.map((item) => {
      const row = byTicker.get(item.ticker);
      return {
        ticker: item.ticker,
        name: item.name,
        composite_score: row?.composite_score ?? null,
        signal_label: row?.signal_label ?? null,
        last_price: row?.last_price ?? null,
        change_1d_pct: row?.change_1d_pct ?? null,
      };
    });
    // Skorlar alınamadıysa eksik veriyi önbelleğe koyma; bir sonraki istek yeniden dener.
    if (screenerRes.ok) cached = { expires: Date.now() + CACHE_MS, rows };
    return NextResponse.json(rows);
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}
