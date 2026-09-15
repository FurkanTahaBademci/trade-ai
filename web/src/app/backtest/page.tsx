import type { Metadata } from "next";
import Link from "next/link";
import { BacktestEquityChart } from "@/components/backtest-equity-chart";
import { EmptyState, PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import type { BacktestRun, BacktestTrade, IndexPrice } from "@/lib/types";
import { BacktestForm } from "@/components/backtest-form";
import { BacktestHistory } from "@/components/backtest-history";
import { BacktestTrades } from "@/components/backtest-trades";

import { normalizeTicker } from "@/lib/turkish";

export const metadata: Metadata = { title: "Backtest" };

type Params = { run?: string; ticker?: string; side?: string };

function dateInput(daysAgo = 0) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const today = Date.parse(`${fields.year}-${fields.month}-${fields.day}T00:00:00Z`);
  return new Date(today - daysAgo * 86400000).toISOString().slice(0, 10);
}

export default async function BacktestPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const runs = await apiGet<BacktestRun[]>("/api/backtests?limit=20", []);
  const requestedId = Number(params.run);
  const selectedId = Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : runs.data[0]?.id;
  const detail = selectedId ? await apiGet<BacktestRun | null>(`/api/backtests/${selectedId}?include_trades=false`, null) : { data: null, ok: true as const };
  const run = detail.data;
  const ticker = params.ticker ? normalizeTicker(params.ticker).slice(0, 16) || undefined : undefined;

  const side = params.side === "BUY" || params.side === "SELL" ? params.side : undefined;
  const query = new URLSearchParams({ limit: "25" });
  if (ticker) query.set("ticker", ticker);
  if (side) query.set("side", side);
  const trades = run ? await apiGet<BacktestTrade[]>(`/api/backtests/${run.id}/trades?${query}`, []) : { data: [], ok: true };
  const indexPrices = run?.status === "COMPLETED"
    ? await apiGet<IndexPrice[]>(`/api/index/XU100/prices?start=${run.start_date}&end=${run.end_date}`, [])
    : { data: [] as IndexPrice[], ok: true as const };
  const serviceDown = !runs.ok || !detail.ok || !trades.ok;

  return <><PageHeader eyebrow="Strateji laboratuvarı · Canlı emir yok" title="Backtest" description="Bileşik sinyal stratejisini geçmiş veride, komisyon ve fiyat kaymasını dahil ederek ölçün. Geçmiş koşulara ve hisse bazında işlemlere ulaşın." actions={<span className="pill pill-primary">backtest-v1</span>}/><ServiceNotice show={serviceDown}/>
    <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-6">
        <section className="panel-flat p-5"><SectionTitle title="Yeni koşu" subtitle="Tarih aralığı ve strateji ayarları"/><BacktestForm startDate={dateInput(365)} endDate={dateInput()}/></section>
        <section><SectionTitle title="Geçmiş koşular" subtitle="Kaydırarak eski değerlendirmelere ulaşın"/><BacktestHistory key={runs.data[0]?.id ?? "empty"} initialItems={runs.data} selectedId={run?.id}/></section>
      </aside>
      <div className="min-w-0">{!run ? <div className="panel-flat"><EmptyState title="Backtest sonucu yok" description="Soldaki ayarlarla ilk koşuyu başlatın. Mevcut geçmiş kısa ise sonuç, yetersiz veri olarak açıkça işaretlenir."/></div> : <>
          <BacktestResult run={run} indexPrices={indexPrices.data}/>
          <section id="islemler" className="mt-6 scroll-mt-24">
            <SectionTitle title="İşlem geçmişi" subtitle="Hisse ve işlem yönüne göre inceleyin"/>
            <form key={`filters-${run.id}-${ticker}-${side}`} method="get" action="/backtest#islemler" className="mb-4 flex flex-wrap items-end gap-3">
              <input type="hidden" name="run" value={run.id}/>
              <label className="min-w-0 flex-1"><span className="mb-1 block text-xs text-[var(--text-muted)]">Hisse kodu</span><input className="input" name="ticker" maxLength={16} placeholder="Örn. THYAO" defaultValue={ticker}/></label>
              <label><span className="mb-1 block text-xs text-[var(--text-muted)]">İşlem yönü</span><select name="side" className="input" defaultValue={side ?? ""}><option value="">Tümü</option><option value="BUY">Alış</option><option value="SELL">Satış</option></select></label>
              <button className="h-10 rounded-[10px] bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)]">Filtrele</button>
              {(ticker || side) && <Link className="py-2 text-xs text-[var(--primary)]" href={`/backtest?run=${run.id}#islemler`}>Temizle</Link>}
            </form>
            {trades.ok ? <BacktestTrades key={`${run.id}-${ticker}-${side}`} initialItems={trades.data} runId={run.id} ticker={ticker} side={side}/> : <p className="text-sm text-[var(--negative)]">İşlemler yüklenemedi. Sayfayı yenileyerek tekrar deneyin.</p>}
          </section>
        </>}</div></div>
  </>;
}


function BacktestResult({ run, indexPrices }: { run: BacktestRun; indexPrices: IndexPrice[] }) {
  const points = run.points ?? [];
  const available = run.status === "COMPLETED";
  return <div className="space-y-6">{run.status === "INSUFFICIENT_DATA" && <div className="rounded-[12px] border px-4 py-3 text-sm text-[var(--warning)]" style={{ borderColor: "color-mix(in srgb, var(--warning) 30%, transparent)", background: "var(--warning-soft)" }}>Seçilen aralıkta güvenilir sonuç üretmek için yeterli sinyal/fiyat günü yok. Sonuç sıfır getiri olarak yorumlanmamalı.</div>}<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Toplam getiri" value={available ? formatPercent(run.total_return_pct, true) : "—"} tone={available ? run.total_return_pct >= 0 : undefined}/><Metric label="Son portföy değeri" value={available ? formatMoney(run.final_equity) : "—"}/><Metric label="Maksimum düşüş" value={available ? formatPercent(-Math.abs(run.max_drawdown_pct)) : "—"}/><Metric label="Sharpe (rf=0)" value={available ? formatNumber(run.sharpe_ratio, 2) : "—"}/><Metric label="Yıllık oynaklık" value={available ? formatPercent(run.annualized_volatility_pct) : "—"}/><Metric label="Kazanma oranı" value={available ? formatPercent(run.win_rate_pct) : "—"} meta={`${run.winning_trades}/${run.closed_trades} kapanan işlem`}/><Metric label="Toplam komisyon" value={formatMoney(run.total_fees)}/><Metric label="Veri kapsamı" value={`${run.signal_count} sinyal`} meta={`${run.price_count} fiyat · ${run.skipped_signal_count} atlandı`}/></div><section className="panel-flat p-5 sm:p-6"><SectionTitle title="Sermaye eğrisi" subtitle={`${run.start_date} → ${run.end_date} · ${points.length} fiyat günü · "Dönem değişimi" görünümünde BIST100 karşılaştırması`}/>{available ? <BacktestEquityChart points={points} indexPrices={indexPrices}/> : <EmptyState compact title="Performans eğrisi için veri yetersiz" description="Sinyal tarihlerinden sonraki fiyatlar toplandığında yeni bir koşu başlatın."/>}</section><section className="panel-flat p-5 text-xs leading-6 text-[var(--text-muted)]"><h2 className="mb-2 text-sm font-semibold text-[var(--text)]">Hesaplama varsayımları</h2><p>Sinyaller aynı gün kapanış verisini içerebildiği için yalnız sonraki mevcut kapanışta uygulanır. Açılış verisi olmadığı için açılış fiyatı tahmin edilmez. %{formatNumber(run.config.fee_rate * 100, 2)} komisyon ve %{formatNumber(run.config.slippage_rate * 100, 2)} olumsuz fiyat kayması kullanılır. Açık pozisyonlar son kapanışla değerlenir, test sonunda varsayımsal satış yapılmaz. Sharpe risksiz faiz oranı sıfır kabul edilerek hesaplanır. BIST100 (XU100) karşılaştırması İş Yatırım'ın resmi endeks verisinden alınır; "Dönem değişimi" görünümünde aynı ilk günden başlayan gerçek getiri olarak gösterilir. Bu ekran yatırım tavsiyesi değildir.</p><p className="mt-2">Koşu #{run.id} · {run.strategy_version} · sinyal modeli {run.signal_model_version} · {formatDate(run.created_at, true)}</p></section></div>;
}

function Metric({ label, value, meta, tone }: { label: string; value: string; meta?: string; tone?: boolean }) { return <div className="panel-flat p-5"><p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">{label}</p><p className={`mt-3 text-xl font-semibold tracking-[-0.03em] ${tone === true ? "text-[var(--positive)]" : tone === false ? "text-[var(--negative)]" : ""}`}>{value}</p>{meta && <p className="mt-1 text-xs text-[var(--text-muted)]">{meta}</p>}</div>; }
