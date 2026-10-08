import { NextResponse } from "next/server";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

type InstrumentRow = { ticker: string; name: string };
type SignalRow = { ticker: string; composite_score: number; signal_label: string };

/** Komut paleti (arama) ve izleme listesi sayfasının kullandığı, tarayıcıdan
 * erişilebilir tek istekli birleşik market özeti. Sunucu tarafında iki
 * genel (kimlik doğrulama gerektirmeyen) uc noktayı birleştirir. */
export async function GET() {
  try {
    const [instrumentsRes, signalsRes] = await Promise.all([
      fetch(`${apiBase()}/api/instruments`, { cache: "no-store", signal: AbortSignal.timeout(15_000) }),
      fetch(`${apiBase()}/api/signals?limit=500`, { cache: "no-store", signal: AbortSignal.timeout(15_000) }),
    ]);
    if (!instrumentsRes.ok) {
      return NextResponse.json({ detail: "Veri servisi yanıt vermedi." }, { status: instrumentsRes.status });
    }
    const instruments = (await instrumentsRes.json()) as InstrumentRow[];
    const signals = instrumentsRes.ok && signalsRes.ok ? ((await signalsRes.json()) as SignalRow[]) : [];
    const signalByTicker = new Map(signals.map((row) => [row.ticker, row]));

    const merged = instruments.map((item) => {
      const signal = signalByTicker.get(item.ticker);
      return {
        ticker: item.ticker,
        name: item.name,
        composite_score: signal?.composite_score ?? null,
        signal_label: signal?.signal_label ?? null,
      };
    });
    return NextResponse.json(merged);
  } catch {
    return NextResponse.json({ detail: "Veri servisine ulaşılamadı." }, { status: 503 });
  }
}
