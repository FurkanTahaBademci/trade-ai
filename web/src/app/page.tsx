import { DataMetric as Metric } from "@/components/ui";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { AIBriefingData, CompositeSignal, Disclosure, FundFlow, MarketHeatmapData, NewsArticle, SystemHealth, SystemStats } from "@/lib/types";
import { formatDate, formatMoney, formatNumber, formatPercent, relativeTime, signalName, sourceName } from "@/lib/format";
import { indexSnapshot, marketMovers, signalDistribution, type FocusResponse, type IndexPoint, type MoverStock } from "@/lib/overview";
import { Icon } from "@/components/icon";
import { EmptyState, ScoreMeter, SectionTitle, ServiceNotice, TickerPills } from "@/components/ui";
import { MarketBriefing } from "@/components/market-briefing";

function isoDaysAgo(days: number) {
  return new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
}

function changeTone(value: number | null | undefined) {
  return value == null || value === 0 ? undefined : value > 0 ? "positive" as const : "negative" as const;
}

function MoverList({ title, items, emptyText }: { title: string; items: MoverStock[]; emptyText: string }) {
  return <div className="min-w-0"><p className="eyebrow px-3 pb-1.5 pt-3">{title}</p>{items.length ? items.map((item) => <Link key={item.ticker} href={`/piyasalar/${item.ticker}`} title={item.name} className="flex items-center gap-2 px-3 py-1.5 text-sm transition hover:bg-[var(--surface-hover)]"><span className="min-w-0 truncate font-semibold text-[var(--primary)]">{item.ticker}</span><span className="terminal-mono ml-auto shrink-0 text-xs font-semibold" style={{ color: item.change_pct > 0 ? "var(--positive)" : "var(--negative)" }}>{formatPercent(item.change_pct, true, 2)}</span></Link>) : <p className="px-3 py-2 text-xs text-[var(--text-muted)]">{emptyText}</p>}</div>;
}

export default async function Home() {
  const [statsRes, news, disclosures, focusRes, flows, signals, health, briefing, heatmap, xu100] = await Promise.all([
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
    apiGet<NewsArticle[]>("/api/news?limit=6&mode=smart", []),
    apiGet<Disclosure[]>("/api/disclosures?limit=5", []),
    apiGet<FocusResponse | null>("/api/ai/focus", null, { revalidate: 60 }),
    apiGet<FundFlow[]>("/api/funds/flows?limit=7", []),
    apiGet<CompositeSignal[]>("/api/signals?limit=5", []),
    apiGet<SystemHealth | null>("/health/detailed", null, { revalidate: 15 }),
    apiGet<AIBriefingData | null>("/api/ai/briefing", null),
    apiGet<MarketHeatmapData | null>("/api/markets/heatmap", null, { revalidate: 60 }),
    apiGet<IndexPoint[]>(`/api/index/XU100/prices?start=${isoDaysAgo(14)}`, [], { revalidate: 300 }),
  ]);
  const focus = focusRes.data?.item ?? null;
  const focusThreshold = focusRes.data?.threshold ?? 30;
  const latestFlow = flows.data[0];
  const servicesUp = health.ok && health.data?.status === "ok";
  const index = indexSnapshot(xu100.data);
  const breadth = heatmap.data?.summary?.total_instruments ? heatmap.data.summary : null;
  const movers = marketMovers(heatmap.data?.sectors.flatMap((sector) => sector.stocks) ?? []);
  const distribution = signalDistribution(statsRes.data?.signals_by_label);

  return <>
    <ServiceNotice show={!news.ok && !signals.ok}/>
    <div className="mb-4 flex flex-col justify-between gap-2 sm:mb-5 sm:flex-row sm:items-end"><div><p className="eyebrow mb-1 sm:mb-2">Piyasa özeti</p><h1 className="page-title">Piyasa terminali</h1><p className="mt-2 hidden text-sm text-[var(--text-secondary)] sm:block">Piyasayı etkileyen veriler tek bir çalışma alanında.</p></div><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><span className={`h-2 w-2 rounded-full ${servicesUp ? "bg-[var(--positive)]" : "bg-[var(--warning)]"}`}/>{servicesUp ? "Veri hatları sağlıklı" : health.ok ? "Veri hatlarında uyarı var" : "Sağlık bilgisi alınamadı"}</div></div>

    <section aria-label="Piyasa göstergeleri" className="mb-4 grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-4">
      <Metric icon="trend" label="BIST 100" value={index ? formatNumber(index.value, 2) : "—"} meta={index ? `${formatPercent(index.changePct, true, 2)} · ${formatDate(index.date)}` : "endeks verisi bekleniyor"} tone={changeTone(index?.changePct)}/>
      <Metric icon="markets" label="Piyasa genişliği" value={breadth ? `${breadth.positive_count} / ${breadth.negative_count}` : "—"} meta={breadth ? `yükselen / düşen · ${breadth.neutral_count} yatay` : "fiyat verisi bekleniyor"} tone={breadth ? changeTone(breadth.positive_count - breadth.negative_count) : undefined}/>
      <Metric icon="ai" label="Sinyal dağılımı" value={distribution ? `${distribution.positive} / ${distribution.negative}` : "—"} meta={distribution ? `pozitif / negatif · ${distribution.neutral} nötr` : "skorlar hesaplanıyor"} tone={distribution ? changeTone(distribution.positive - distribution.negative) : undefined}/>
      <Metric icon="funds" label="Fon hisse akımı" value={formatMoney(latestFlow?.estimated_stock_flow, true)} meta={latestFlow ? `${formatDate(latestFlow.date)} · ${formatPercent(latestFlow.positive_flow_pct)} pozitif` : "veri bekleniyor"} tone={changeTone(latestFlow?.estimated_stock_flow)}/>
    </section>

    <section className="panel mb-4 overflow-hidden">{focus ? <div className="flex items-start gap-3 p-4 sm:items-center sm:gap-4"><div className="hidden h-11 w-11 shrink-0 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)] sm:grid"><Icon name="spark" size={21}/></div><div className="min-w-0 flex-1"><div className="mb-1.5 flex flex-wrap items-center gap-2"><span className="eyebrow">AI gündem özeti</span><span className="pill pill-primary">{focus.event_label}</span><span className={`pill ${focus.impact === "POSITIVE" ? "pill-positive" : focus.impact === "NEGATIVE" ? "pill-negative" : ""}`}>{focus.impact === "POSITIVE" ? "Pozitif" : focus.impact === "NEGATIVE" ? "Negatif" : "Nötr"}</span></div><Link href={focus.href} className="hover:text-[var(--primary)]"><h2 className="text-base font-semibold leading-6 tracking-[-0.02em] sm:text-lg sm:leading-7">{focus.title}</h2></Link>{focus.description && <p className="mt-1 line-clamp-2 text-sm text-[var(--text-secondary)]">{focus.description}</p>}<div className="mt-2.5 flex flex-wrap items-center gap-3"><TickerPills tickers={focus.tickers}/>{focus.published_at && <span className="text-xs text-[var(--text-muted)]">{relativeTime(focus.published_at)}</span>}</div></div><div className="flex shrink-0 flex-col items-end gap-2"><ScoreMeter score={focus.impact_score} label="Etki" size={64}/><Link href={`/analizler/${focus.evaluation_id}`} className="icon-button" aria-label="AI analizini aç"><Icon name="arrow"/></Link></div></div> : <div className="flex items-center gap-3 px-4 py-3"><Icon name="spark" size={16} className="shrink-0 text-[var(--text-muted)]"/><p className="text-sm text-[var(--text-secondary)]"><span className="font-medium text-[var(--text)]">Gündem sakin.</span> Son 24 saatte AI etki puanı {focusThreshold} ve üzeri haber/KAP gelişmesi yok.</p></div>}<div className="border-t px-4 py-2 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>AI çıktıları bilgi amaçlıdır; yatırım tavsiyesi veya al-sat sinyali değildir.</div></section>

    <div className="mb-5 grid gap-4 lg:grid-cols-2">
      <section className="min-w-0"><SectionTitle title="Bileşik sıralama" subtitle="En yüksek bileşik skorlar" href="/sinyaller"/><div className="panel-flat overflow-hidden">{signals.data.length ? signals.data.map((item, index) => <Link href={`/piyasalar/${item.ticker}`} key={item.id} className={`flex items-center gap-3 px-3.5 py-2.5 transition hover:bg-[var(--surface-hover)] ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><span className="w-5 text-center text-[11px] font-semibold text-[var(--text-muted)]">{index + 1}</span><span className="font-semibold text-[var(--primary)]">{item.ticker}</span><span className={`pill ml-auto ${item.signal_label.includes("POSITIVE") ? "pill-positive" : item.signal_label.includes("NEGATIVE") ? "pill-negative" : ""}`}>{signalName(item.signal_label)}</span><span className="w-8 text-right text-sm font-semibold">{Math.round(item.composite_score)}</span></Link>) : <EmptyState compact title="Skorlar hesaplanıyor"/>}</div></section>
      <section className="min-w-0"><SectionTitle title="Günün hareketlileri" subtitle={heatmap.data?.as_of_date ? `${formatDate(heatmap.data.as_of_date)} kapanışı · sığ hisseler hariç` : "Günlük değişim"} href="/piyasalar"/><div className="panel-flat grid grid-cols-2 divide-x divide-[var(--border)] pb-2">{heatmap.data ? <><MoverList title="En çok yükselen" items={movers.gainers} emptyText="Yükselen hisse yok"/><MoverList title="En çok düşen" items={movers.losers} emptyText="Düşen hisse yok"/></> : <div className="col-span-2"><EmptyState compact title="Fiyat verisi alınamadı"/></div>}</div></section>
    </div>

    <MarketBriefing briefing={briefing.data} />

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(330px,.75fr)]">
      <div className="min-w-0 space-y-4">
        <section><SectionTitle title="Öne çıkan haberler" subtitle="AI önem puanı ve güncellik sıralaması" href="/haberler"/><div className="panel-flat overflow-hidden">{news.data.length ? news.data.map((item, i) => <article key={item.id} className={`group grid gap-3 p-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[100px_minmax(0,1fr)_auto] sm:items-center ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div><span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{sourceName(item.source)}</span><p className="mt-1 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</p></div><div className="min-w-0"><div className="mb-1 flex items-center gap-2"><Link href={`/haberler/${item.id}`}><h3 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.title}</h3></Link>{item.impact_score != null && item.impact_score > 0 && <span className={`pill shrink-0 text-[10px] font-semibold ${item.impact_score >= 40 ? "pill-primary" : "bg-[var(--surface-raised)]"}`}>Etki: {item.impact_score}</span>}</div><div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></article>) : <EmptyState compact/>}</div></section>
      </div>

      <div className="space-y-4">
        <section><SectionTitle title="Son KAP bildirimleri" subtitle="Şirket açıklamaları" href="/kap"/><div className="panel-flat overflow-hidden">{disclosures.data.length ? disclosures.data.map((item, i) => <article key={item.disclosure_index} className={`block p-4 transition hover:bg-[var(--surface-hover)] ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div className="mb-2 flex items-center justify-between gap-3"><TickerPills tickers={item.ticker_codes}/><span className="shrink-0 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</span></div><Link href={`/kap/${item.disclosure_index}`} className="hover:text-[var(--primary)]"><p className="line-clamp-2 text-sm font-medium leading-5">{item.subject || item.summary || item.kap_title}</p></Link>{item.attachment_count > 0 && <p className="mt-2 flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><Icon name="file" size={12}/>{item.attachment_count} ek dosya</p>}</article>) : <EmptyState compact/>}</div></section>
        <section><SectionTitle title="Veri kaynakları" subtitle="Sistem bağlantı durumu"/><div className="panel-flat divide-y divide-[var(--border)]">{health.data?.monitoring ? Object.values(health.data.monitoring.collectors).map((item) => <div key={item.name} className="flex items-center gap-3 px-3 py-2.5"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${item.state === "healthy" ? "bg-[var(--positive)]" : item.state === "error" ? "bg-[var(--negative)]" : item.state === "disabled" ? "bg-[var(--text-muted)]" : "bg-[var(--warning)]"}`}/><span className="text-xs">{item.label}</span><span className="ml-auto text-[10px] text-[var(--text-muted)]">{{ healthy: "Sağlıklı", stale: "Gecikmiş", error: "Hata", pending: "Bekleniyor", disabled: "Devre dışı" }[item.state]}</span></div>) : <EmptyState compact title="Kaynak durumu alınamadı"/>}</div></section>
      </div>
    </div>
  </>;
}
