import { DataMetric as Metric } from "@/components/ui";
import type { Metadata } from "next";
import Link from "next/link";
import { BacktestEquityChart } from "@/components/backtest-equity-chart";
import { EmptyState, PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import type { BacktestQuota, BacktestRobustness, BacktestRun, BacktestTrade, IndexPrice } from "@/lib/types";
import { BacktestForm } from "@/components/backtest-form";
import { BacktestHistory } from "@/components/backtest-history";
import { BacktestTrades } from "@/components/backtest-trades";
import { LogoutButton } from "@/components/logout-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { redirect } from "next/navigation";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import { isAdminRequest } from "@/lib/admin-request";
import { deleteBacktestAction, startPaperFromBacktestAction } from "./actions";

import { normalizeTicker } from "@/lib/turkish";

export const metadata: Metadata = { title: "Backtest" };

type Params = { run?: string; ticker?: string; side?: string; result?: string; message?: string };

function dateInput(daysAgo = 0) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const today = Date.parse(`${fields.year}-${fields.month}-${fields.day}T00:00:00Z`);
  return new Date(today - daysAgo * 86400000).toISOString().slice(0, 10);
}

export default async function BacktestPage({ searchParams }: { searchParams: Promise<Params> }) {
  const [params, account, token] = await Promise.all([searchParams, currentAccount(), sessionToken()]);
  // Hesapla girenler kendi koşularını, yerleşik (ortam değişkenli) yönetici sistem koşularını görür.
  const personal = Boolean(account && token);
  if (!personal && !(await isAdminRequest())) redirect("/giris?next=/backtest");
  const base = personal ? "/api/me/backtests" : "/api/backtests";
  async function load<T>(path: string, fallback: T): Promise<{ data: T; ok: boolean }> {
    if (!personal) return apiGet<T>(path, fallback);
    const result = await accountRequest<T>(path, token!);
    // Silinmiş ya da başkasına ait koşu: seçili koşu yokmuş gibi davran.
    return result.ok ? { data: result.data, ok: true } : { data: fallback, ok: result.status === 404 };
  }
  const [runs, quota] = await Promise.all([
    load<BacktestRun[]>(`${base}?limit=20`, []),
    personal ? load<BacktestQuota | null>("/api/me/backtests/quota", null) : Promise.resolve({ data: null, ok: true }),
  ]);
  const requestedId = Number(params.run);
  const selectedId = Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : runs.data[0]?.id;
  const detail = selectedId ? await load<BacktestRun | null>(`${base}/${selectedId}?include_trades=false`, null) : { data: null, ok: true as const };
  const run = detail.data;
  const ticker = params.ticker ? normalizeTicker(params.ticker).slice(0, 16) || undefined : undefined;

  const side = params.side === "BUY" || params.side === "SELL" ? params.side : undefined;
  const query = new URLSearchParams({ limit: "25" });
  if (ticker) query.set("ticker", ticker);
  if (side) query.set("side", side);
  const finished = run?.status === "COMPLETED" || run?.status === "INSUFFICIENT_DATA";
  const trades = run && finished ? await load<BacktestTrade[]>(`${base}/${run.id}/trades?${query}`, []) : { data: [] as BacktestTrade[], ok: true };
  const indexPrices = run?.status === "COMPLETED"
    ? await apiGet<IndexPrice[]>(`/api/index/XU100/prices?start=${run.start_date}&end=${run.end_date}`, [])
    : { data: [] as IndexPrice[], ok: true as const };
  const serviceDown = !runs.ok || !detail.ok || !trades.ok;
  const quotaText = quota.data ? (quota.data.exempt ? "Yönetici hesabı · sınır yok" : `Bugün ${quota.data.used_today}/${quota.data.daily_limit} koşu · aynı anda ${quota.data.max_active}`) : "Tarih aralığı ve strateji ayarları";

  return <><PageHeader eyebrow="Strateji laboratuvarı · Canlı emir yok" title="Backtest" description={personal ? "Bileşik sinyal stratejisini kendi ayarlarınla geçmiş veride, komisyon ve fiyat kaymasını dahil ederek ölç. Koşular sırayla hesaplanır; sonuç çoğunlukla bir dakikadan kısa sürede gelir. Koşuların yalnız sana görünür." : "Sistem (yönetici) koşuları. Bileşik sinyal stratejisini geçmiş veride, komisyon ve fiyat kaymasını dahil ederek ölçün."} actions={<div className="flex items-center gap-2">{run && <span className="pill pill-primary">{run.strategy_version}</span>}<LogoutButton/></div>}/><ServiceNotice show={serviceDown}/>
    {params.message && <div role="status" className={`mb-5 rounded border px-4 py-3 text-sm ${params.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: params.result === "ok" ? "var(--positive)" : "var(--negative)", background: params.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{params.message}</div>}
    <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-4">
        <section className="panel-flat p-4"><SectionTitle title="Yeni koşu" subtitle={quotaText}/><BacktestForm startDate={dateInput(365)} endDate={dateInput()}/></section>
        <section><SectionTitle title="Geçmiş koşular" subtitle="Kaydırarak eski değerlendirmelere ulaşın"/><BacktestHistory key={`${personal}-${runs.data[0]?.id ?? "empty"}-${runs.data[0]?.status}`} initialItems={runs.data} selectedId={run?.id} endpoint={personal ? "/api/hesap/backtests" : "/api/list-feed/backtests"}/></section>
      </aside>
      <div className="min-w-0">{!run ? <div className="panel-flat"><EmptyState title="Backtest sonucu yok" description="Soldaki ayarlarla ilk koşuyu başlatın. Mevcut geçmiş kısa ise sonuç, yetersiz veri olarak açıkça işaretlenir."/></div> : <>
          <BacktestResult run={run} indexPrices={indexPrices.data} personal={personal}/>
          {finished && <section id="islemler" className="mt-6 scroll-mt-24">
            <SectionTitle title="İşlem geçmişi" subtitle="Hisse ve işlem yönüne göre inceleyin"/>
            <form key={`filters-${run.id}-${ticker}-${side}`} method="get" action="/backtest#islemler" className="mb-4 flex flex-wrap items-end gap-3">
              <input type="hidden" name="run" value={run.id}/>
              <label className="min-w-0 flex-1"><span className="mb-1 block text-xs text-[var(--text-muted)]">Hisse kodu</span><input className="input" name="ticker" maxLength={16} placeholder="Örn. THYAO" defaultValue={ticker}/></label>
              <label><span className="mb-1 block text-xs text-[var(--text-muted)]">İşlem yönü</span><select name="side" className="input" defaultValue={side ?? ""}><option value="">Tümü</option><option value="BUY">Alış</option><option value="SELL">Satış</option></select></label>
              <button className="h-10 rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)]">Filtrele</button>
              {(ticker || side) && <Link className="py-2 text-xs text-[var(--primary)]" href={`/backtest?run=${run.id}#islemler`}>Temizle</Link>}
            </form>
            {trades.ok ? <BacktestTrades key={`${run.id}-${ticker}-${side}`} initialItems={trades.data} endpoint={personal ? `/api/hesap/backtests/${run.id}/trades` : `/api/backtest-trades/${run.id}`} ticker={ticker} side={side}/> : <p className="text-sm text-[var(--negative)]">İşlemler yüklenemedi. Sayfayı yenileyerek tekrar deneyin.</p>}
          </section>}
        </>}</div></div>
  </>;
}


function BacktestResult({ run, indexPrices, personal }: { run: BacktestRun; indexPrices: IndexPrice[]; personal: boolean }) {
  if (run.status === "QUEUED" || run.status === "RUNNING") return <RunPending run={run}/>;
  if (run.status === "FAILED") return <div role="alert" className="panel-flat p-5"><p className="text-sm font-semibold text-[var(--negative)]">Koşu tamamlanamadı</p><p className="mt-1.5 text-xs leading-5 text-[var(--text-secondary)]">{run.error ?? "Beklenmeyen bir hata oluştu."} Aynı ayarlarla yeniden başlatabilirsin.</p>{personal && <DeleteRun runId={run.id}/>}</div>;
  const points = run.points ?? [];
  const available = run.status === "COMPLETED";
  const exposure = averageExposure(points);
  const basket = run.config.strategy === "basket";
  const weights = run.config.component_weights;
  return <div className="space-y-4">{run.status === "INSUFFICIENT_DATA" && <div className="rounded border px-4 py-3 text-sm text-[var(--warning)]" style={{ borderColor: "color-mix(in srgb, var(--warning) 30%, transparent)", background: "var(--warning-soft)" }}>Seçilen aralıkta güvenilir sonuç üretmek için yeterli sinyal/fiyat günü yok. Sonuç sıfır getiri olarak yorumlanmamalı.</div>}<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><Metric label="Toplam getiri" value={available ? formatPercent(run.total_return_pct, true) : "—"} tone={available ? (run.total_return_pct ?? 0) >= 0 : undefined}/><Metric label="Son portföy değeri" value={available ? formatMoney(run.final_equity) : "—"}/><Metric label="Maksimum düşüş" value={available ? formatPercent(-Math.abs(run.max_drawdown_pct ?? 0)) : "—"}/><Metric label="Sharpe (rf=0)" value={available ? formatNumber(run.sharpe_ratio, 2) : "—"}/><Metric label="Yıllık oynaklık" value={available ? formatPercent(run.annualized_volatility_pct) : "—"}/><Metric label="Kazanma oranı" value={available ? formatPercent(run.win_rate_pct) : "—"} meta={`${run.winning_trades}/${run.closed_trades} kapanan işlem`}/><Metric label="Toplam komisyon" value={formatMoney(run.total_fees ?? 0)}/><Metric label="Ortalama yatırım oranı" value={available && exposure != null ? formatPercent(exposure) : "—"} meta="Sermayenin hisselerde olan kısmı; düşük oran sonucu nakit belirler"/><Metric label="Veri kapsamı" value={`${run.signal_count} sinyal`} meta={`${run.price_count} fiyat · ${run.skipped_signal_count} atlandı`}/></div>{available && run.robustness && <RobustnessPanel robustness={run.robustness}/>}<section className="panel-flat p-4"><SectionTitle title="Sermaye eğrisi" subtitle={`${run.start_date} → ${run.end_date} · ${points.length} fiyat günü · "Dönem değişimi" görünümünde BIST100 karşılaştırması`}/>{available ? <BacktestEquityChart points={points} indexPrices={indexPrices}/> : <EmptyState compact title="Performans eğrisi için veri yetersiz" description="Sinyal tarihlerinden sonraki fiyatlar toplandığında yeni bir koşu başlatın."/>}</section><section className="panel-flat p-4 text-xs leading-6 text-[var(--text-muted)]"><h2 className="mb-2 text-sm font-semibold text-[var(--text)]">Hesaplama varsayımları</h2><p>{basket ? `Strateji: sıralama sepeti. Her ${run.config.rebalance_days} işlem gününde, o günden önceki son skorlara göre en yüksek skorlu ${run.config.basket_size} likit hisse eşit ağırlıkla tutulur; elde olan hisse ilk ${run.config.basket_keep} içinde kaldıkça satılmaz. Giriş/çıkış skoru, zarar-kes ve pozisyon sınırları bu stratejide kullanılmaz. ` : `Strateji: eşik. Skor ${formatNumber(run.config.entry_score, 0)} ve üzerine çıkan hisse alınır, ${formatNumber(run.config.exit_score, 0)} altına inen satılır. `}{weights ? `Ağırlık simülasyonu: skor, saklanan bileşen skorlarından ${weightText(weights)} ağırlıklarıyla yeniden hesaplanmıştır (bileşen güvenleri kaydedilmeden önceki günlerde kayıtlı toplam güven kullanılır). ` : ""}Sinyaller aynı gün kapanış verisini içerebildiği için yalnız sonraki mevcut kapanışta uygulanır. Açılış verisi olmadığı için açılış fiyatı tahmin edilmez. %{formatNumber(run.config.fee_rate * 100, 2)} komisyon ve %{formatNumber(run.config.slippage_rate * 100, 2)} olumsuz fiyat kayması kullanılır. {run.config.stop_loss_pct ? `Kapanış ortalama maliyetin %${formatNumber(run.config.stop_loss_pct, 1)} altına inerse pozisyon o kapanışta satılır (zarar-kes) ve aynı gün yeniden alınmaz. ` : "Zarar-kes uygulanmaz. "}{run.config.max_new_entries_per_day ? `Bir günde en fazla ${run.config.max_new_entries_per_day} yeni pozisyon açılır.` : "Günlük yeni pozisyon sınırı yoktur."} {run.config.price_limit_pct ? `Günü %${formatNumber(run.config.price_limit_pct, 1)} ve üzeri yükselişle (tavan) kapatan hisse o kapanıştan alınmaz, aynı oranda düşüşle (taban) kapatan satılmaz; satış ertesi işlem gününe kalır. ` : "Tavan/taban kuralı uygulanmaz; bu, sığ hisselerde sonucu olduğundan iyi gösterebilir. "}{run.config.min_avg_volume ? `Son 20 işlem günü ortalama hacmi ${formatMoney(run.config.min_avg_volume, true)} altındaki hisselere girilmez. ` : ""}{run.config.regime_ma_days ? `XU100 ${run.config.regime_ma_days} günlük ortalamasının altındayken yeni pozisyon açılmaz. ` : ""}{run.config.max_volatility_pct ? `Son 20 işlem günü günlük getiri oynaklığı %${formatNumber(run.config.max_volatility_pct, 1)} üstündeki hisselere girilmez.` : ""} Açık pozisyonlar son kapanışla değerlenir, test sonunda varsayımsal satış yapılmaz. Sharpe risksiz faiz oranı sıfır kabul edilerek hesaplanır. BIST100 (XU100) karşılaştırması İş Yatırım'ın resmi endeks verisinden alınır; "Dönem değişimi" görünümünde aynı ilk günden başlayan gerçek getiri olarak gösterilir. Bu ekran yatırım tavsiyesi değildir.</p><p className="mt-2">Koşu #{run.id} · {run.strategy_version} · sinyal modeli {run.signal_model_version} · {formatDate(run.created_at, true)}</p></section>{personal && <PaperBridge run={run}/>}</div>;
}

const STATUS_TEXT = { QUEUED: "Sırada bekliyor", RUNNING: "Hesaplanıyor" } as const;

function RunPending({ run }: { run: BacktestRun }) {
  return <div role="status" className="panel-flat p-6 text-center">
    <AutoRefresh intervalMs={3000}/>
    <span className="mx-auto mb-3 block h-8 w-8 animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--primary)]" aria-hidden="true"/>
    <p className="text-sm font-semibold">Koşu #{run.id} · {STATUS_TEXT[run.status as keyof typeof STATUS_TEXT]}</p>
    <p className="mt-1.5 text-xs leading-5 text-[var(--text-muted)]">{run.start_date} → {run.end_date}. Koşular sırayla hesaplanır; bu sayfa birkaç saniyede bir kendini yeniler.</p>
  </div>;
}

function DeleteRun({ runId }: { runId: number }) {
  return <form action={deleteBacktestAction} className="mt-3"><input type="hidden" name="run_id" value={runId}/><button className="pill hover:text-[var(--negative)]">Koşuyu sil</button></form>;
}

/** Eşik stratejili, ağırlık simülasyonsuz koşunun ayarlarıyla strateji portföyü açar. */
function PaperBridge({ run }: { run: BacktestRun }) {
  const supported = run.status === "COMPLETED" && run.config.strategy !== "basket" && !run.config.component_weights;
  return <section className="panel-flat p-4">
    <SectionTitle title="Bu ayarlarla paper portföy başlat" subtitle={supported ? "Strateji bugünden itibaren canlı sinyallerle sanal olarak izlenir" : "Bu koşu türü paper portföye aktarılamaz"}/>
    {supported ? <form action={startPaperFromBacktestAction} className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <input type="hidden" name="run_id" value={run.id}/>
      <label className="min-w-0 flex-1"><span className="mb-1 block text-xs text-[var(--text-muted)]">Portföy adı</span><input className="input" name="name" maxLength={64} required defaultValue={`Backtest #${run.id}`}/></label>
      <label><span className="mb-1 block text-xs text-[var(--text-muted)]">Başlangıç bakiyesi</span><select className="input" name="initial_cash" defaultValue="1000000"><option value="100000">100.000 TL</option><option value="1000000">1.000.000 TL</option><option value="10000000">10.000.000 TL</option></select></label>
      <button className="h-10 shrink-0 rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Portföyü başlat</button>
    </form> : <p className="text-xs leading-5 text-[var(--text-muted)]">Sıralama sepeti ve ağırlık simülasyonu paper portföyde yok; eşik stratejisiyle koşulan testleri aktarabilirsin.</p>}
    {supported && <p className="mt-3 text-[10px] leading-4 text-[var(--text-muted)]">Giriş/çıkış skoru, güven, kaynak sayısı, pozisyon sayısı ve ağırlığı, günlük yeni alım ve zarar-kes aktarılır. Komisyon, kayma, tavan/taban ve hacim kuralları paper'da herkes için sabittir; kâr-al, takip eden stop ve sektör tavanı kapalı başlar, portföy sayfasından açılabilir. Geçmiş sonuç gelecekteki getiriyi garanti etmez.</p>}
    <DeleteRun runId={run.id}/>
  </section>;
}

const weightLabels: Record<string, string> = { llm: "AI etkisi", fundamental: "temel analiz", analyst: "analist", momentum: "momentum" };

function weightText(weights: Record<string, number>) {
  return Object.entries(weights).map(([name, value]) => `${weightLabels[name] ?? name} %${formatNumber(value * 100, 0)}`).join(", ");
}

function averageExposure(points: { positions_value: number; total_equity: number }[]) {
  const ratios = points.filter((point) => point.total_equity > 0).map((point) => (point.positions_value / point.total_equity) * 100);
  return ratios.length ? ratios.reduce((sum, value) => sum + value, 0) / ratios.length : null;
}

function RobustnessPanel({ robustness }: { robustness: BacktestRobustness }) {
  const tone = (value: number | null) => value == null ? "" : value >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
  return <section className="panel-flat p-4">
    <SectionTitle title="Başlangıç günü hassasiyeti" subtitle={`Aynı ayarlar, başlangıç ${robustness.shifts_trading_days.slice(1).join(", ")} işlem günü kaydırılarak tekrarlandı · ${robustness.beat_benchmark_runs}/${robustness.runs.length} koşu XU100'ü geçti`}/>
    <div className="mb-3 grid gap-3 sm:grid-cols-3"><Metric label="XU100'e fark (ortalama)" value={formatPercent(robustness.excess_mean_pct, true)} tone={robustness.excess_mean_pct != null ? robustness.excess_mean_pct >= 0 : undefined}/><Metric label="En kötü" value={formatPercent(robustness.excess_min_pct, true)}/><Metric label="En iyi" value={formatPercent(robustness.excess_max_pct, true)}/></div>
    <div className="table-shell overflow-x-auto"><table className="data-table min-w-[480px]"><thead><tr><th>Başlangıç</th><th className="text-right">Getiri</th><th className="text-right">XU100</th><th className="text-right">Fark</th></tr></thead><tbody>{robustness.runs.map((item, index) => <tr key={item.start_date}><td>{formatDate(item.start_date)}{index === 0 && <span className="pill ml-1.5">ana koşu</span>}</td><td className={`text-right ${tone(item.total_return_pct)}`}>{formatPercent(item.total_return_pct, true)}</td><td className="text-right">{formatPercent(item.benchmark_return_pct, true)}</td><td className={`text-right font-medium ${tone(item.excess_return_pct)}`}>{formatPercent(item.excess_return_pct, true)}</td></tr>)}</tbody></table></div>
    <p className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">Koşular arasındaki fark büyükse sonuç stratejiden çok takvim şansına bağlıdır; karar için ortalamaya ve en kötü koşuya bakın.</p>
  </section>;
}
