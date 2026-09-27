import { DataMetric as Metric } from "@/components/ui";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { AIBriefingData, CompositeSignal, Disclosure, Evaluation, FundFlow, NewsArticle, SystemHealth, SystemStats } from "@/lib/types";
import { eventName, formatDate, formatMoney, formatPercent, relativeTime, signalName, sourceName } from "@/lib/format";
import { Icon } from "@/components/icon";
import { EmptyState, ScoreMeter, SectionTitle, ServiceNotice, TickerPills } from "@/components/ui";
import { MarketBriefing } from "@/components/market-briefing";

export default async function Home() {
  const [statsRes, news, disclosures, evaluations, flows, signals, health, briefing] = await Promise.all([
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
    apiGet<NewsArticle[]>("/api/news?limit=6&mode=smart", []),
    apiGet<Disclosure[]>("/api/disclosures?limit=5", []),
    apiGet<Evaluation[]>("/api/evaluations?status=succeeded&limit=20", []),
    apiGet<FundFlow[]>("/api/funds/flows?limit=7", []),
    apiGet<CompositeSignal[]>("/api/signals?limit=5", []),
    apiGet<SystemHealth | null>("/health/detailed", null, { revalidate: 15 }),
    apiGet<AIBriefingData | null>("/api/ai/briefing", null),
  ]);
  const stats = statsRes.data;
  const focus = evaluations.data.find((item) => item.summary && item.impact_score != null);
  const latestFlow = flows.data[0];
  const servicesUp = health.ok && health.data?.status === "ok";

  return <>
    <ServiceNotice show={!news.ok && !signals.ok}/>
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="eyebrow mb-2">Piyasa özeti</p><h1 className="page-title">Piyasa terminali</h1><p className="mt-2 text-sm text-[var(--text-secondary)]">Piyasayı etkileyen veriler tek bir çalışma alanında.</p></div><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><span className={`h-2 w-2 rounded-full ${servicesUp ? "bg-[var(--positive)]" : "bg-[var(--warning)]"}`}/>{servicesUp ? "Veri hatları sağlıklı" : health.ok ? "Veri hatlarında uyarı var" : "Sağlık bilgisi alınamadı"}</div></div>

    <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon="markets" label="Takip evreni" value={stats?.instruments_total ? stats.instruments_total.toLocaleString("tr-TR") : "—"} meta="aktif BIST hissesi"/>
      <Metric icon="news" label="Haber havuzu" value={stats?.news_total ? stats.news_total.toLocaleString("tr-TR") : (news.ok ? String(news.data.length) : "—")} meta="toplam haber"/>
      <Metric icon="ai" label="Bileşik sinyal" value={stats?.signals_total ? stats.signals_total.toLocaleString("tr-TR") : (signals.ok ? String(signals.data.length) : "—")} meta="aktif sinyal"/>
      <Metric icon="funds" label="Fon hisse akımı" value={formatMoney(latestFlow?.estimated_stock_flow, true)} meta={latestFlow ? `${formatDate(latestFlow.date)} · ${formatPercent(latestFlow.positive_flow_pct)} pozitif` : "veri bekleniyor"} tone={(latestFlow?.estimated_stock_flow ?? 0) >= 0 ? "positive" : "negative"}/>
    </section>

    <MarketBriefing briefing={briefing.data} />

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(330px,.75fr)]">
      <div className="space-y-4">
        <section className="panel overflow-hidden"><div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:p-4"><div className="grid h-11 w-11 shrink-0 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="spark" size={21}/></div>{focus ? <><div className="min-w-0 flex-1"><div className="mb-2 flex flex-wrap items-center gap-2"><span className="eyebrow">AI gündem özeti</span><span className="pill pill-primary">{eventName(focus.event_type)}</span></div><h2 className="text-lg font-semibold leading-7 tracking-[-0.025em]">{focus.summary}</h2><div className="mt-3 flex items-center gap-3"><TickerPills tickers={focus.ticker_codes}/><span className="text-xs text-[var(--text-muted)]">{relativeTime(focus.created_at)}</span></div></div><ScoreMeter score={focus.impact_score} label="Etki"/><Link href={`/analizler/${focus.id}`} className="icon-button shrink-0"><Icon name="arrow"/></Link></> : <div className="flex-1"><p className="eyebrow mb-2">AI gündem özeti</p><h2 className="text-base font-semibold">Değerlendirme akışı hazır</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Gemini değerlendirmeleri çalıştığında en etkili gelişme burada öne çıkarılacak.</p></div>}</div><div className="border-t px-5 py-3 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>AI çıktıları bilgi amaçlıdır; yatırım tavsiyesi veya al-sat sinyali değildir.</div></section>

        <section><SectionTitle title="Öne çıkan haberler" subtitle="AI önem puanı ve güncellik sıralaması" href="/haberler"/><div className="panel-flat overflow-hidden">{news.data.length ? news.data.map((item, i) => <article key={item.id} className={`group grid gap-3 p-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[100px_minmax(0,1fr)_auto] sm:items-center ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div><span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{sourceName(item.source)}</span><p className="mt-1 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</p></div><div className="min-w-0"><div className="mb-1 flex items-center gap-2"><Link href={`/haberler/${item.id}`}><h3 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.title}</h3></Link>{item.impact_score != null && item.impact_score > 0 && <span className={`pill shrink-0 text-[10px] font-semibold ${item.impact_score >= 40 ? "pill-primary" : "bg-[var(--surface-raised)]"}`}>Etki: {item.impact_score}</span>}</div><div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></article>) : <EmptyState compact/>}</div></section>
      </div>

      <div className="space-y-4">
        <section><SectionTitle title="Bileşik sıralama" subtitle="Güncel teknik görünüm" href="/sinyaller"/><div className="panel-flat overflow-hidden">{signals.data.length ? signals.data.map((item, index) => <Link href={`/piyasalar/${item.ticker}`} key={item.id} className={`flex items-center gap-3 p-3.5 transition hover:bg-[var(--surface-hover)] ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><span className="w-5 text-center text-[11px] font-semibold text-[var(--text-muted)]">{index + 1}</span><span className="font-semibold text-[var(--primary)]">{item.ticker}</span><span className={`pill ml-auto ${item.signal_label.includes("POSITIVE") ? "pill-positive" : item.signal_label.includes("NEGATIVE") ? "pill-negative" : ""}`}>{signalName(item.signal_label)}</span><span className="w-8 text-right text-sm font-semibold">{Math.round(item.composite_score)}</span></Link>) : <EmptyState compact title="Skorlar hesaplanıyor"/>}</div></section>
        <section><SectionTitle title="Son KAP bildirimleri" subtitle="Şirket açıklamaları" href="/kap"/><div className="panel-flat overflow-hidden">{disclosures.data.length ? disclosures.data.map((item, i) => <article key={item.disclosure_index} className={`block p-4 transition hover:bg-[var(--surface-hover)] ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div className="mb-2 flex items-center justify-between gap-3"><TickerPills tickers={item.ticker_codes}/><span className="shrink-0 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</span></div><Link href={`/kap/${item.disclosure_index}`} className="hover:text-[var(--primary)]"><p className="line-clamp-2 text-sm font-medium leading-5">{item.subject || item.summary || item.kap_title}</p></Link>{item.attachment_count > 0 && <p className="mt-2 flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><Icon name="file" size={12}/>{item.attachment_count} ek dosya</p>}</article>) : <EmptyState compact/>}</div></section>
        <section><SectionTitle title="Veri kaynakları" subtitle="Sistem bağlantı durumu"/><div className="panel-flat divide-y divide-[var(--border)]">{health.data?.monitoring ? Object.values(health.data.monitoring.collectors).map((item) => <div key={item.name} className="flex items-center gap-3 px-3 py-2.5"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${item.state === "healthy" ? "bg-[var(--positive)]" : item.state === "error" ? "bg-[var(--negative)]" : "bg-[var(--warning)]"}`}/><span className="text-xs">{item.label}</span><span className="ml-auto text-[10px] text-[var(--text-muted)]">{{ healthy: "Sağlıklı", stale: "Gecikmiş", error: "Hata", pending: "Bekleniyor" }[item.state]}</span></div>) : <EmptyState compact title="Kaynak durumu alınamadı"/>}</div></section>
      </div>
    </div>
  </>;
}
