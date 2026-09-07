import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Disclosure, Evaluation, FundFlow, Instrument, NewsArticle } from "@/lib/types";
import { eventName, formatDate, formatMoney, formatPercent, relativeTime, sourceName } from "@/lib/format";
import { Icon } from "@/components/icon";
import { EmptyState, ScoreRing, SectionTitle, ServiceNotice, TickerPills } from "@/components/ui";

export default async function Home() {
  const [instruments, news, disclosures, evaluations, flows, health] = await Promise.all([
    apiGet<Instrument[]>("/api/instruments", []), apiGet<NewsArticle[]>("/api/news?limit=6", []), apiGet<Disclosure[]>("/api/disclosures?limit=5", []),
    apiGet<Evaluation[]>("/api/evaluations?status=succeeded&limit=20", []), apiGet<FundFlow[]>("/api/funds/flows?limit=7", []), apiGet<Record<string, unknown>>("/health/detailed", {}),
  ]);
  const focus = evaluations.data.find((item) => item.summary && item.impact_score != null);
  const latestFlow = flows.data[0];
  const servicesUp = health.ok;

  return <>
    <ServiceNotice show={!instruments.ok && !news.ok}/>
    <div className="mb-7 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="eyebrow mb-2">Piyasa özeti</p><h1 className="page-title">Günaydın, Furkan.</h1><p className="mt-2 text-sm text-[var(--text-secondary)]">Piyasayı etkileyen veriler tek bir çalışma alanında.</p></div><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><span className={`h-2 w-2 rounded-full ${servicesUp ? "bg-[var(--positive)]" : "bg-[var(--warning)]"}`}/>{servicesUp ? "Tüm sistemler çalışıyor" : "Servis bağlantısı bekleniyor"}</div></div>

    <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon="markets" label="Takip evreni" value={instruments.ok ? instruments.data.length.toLocaleString("tr-TR") : "—"} meta="aktif BIST hissesi"/>
      <Metric icon="news" label="Son haberler" value={news.ok ? String(news.data.length) : "—"} meta="güncel akışta"/>
      <Metric icon="ai" label="AI değerlendirme" value={evaluations.ok ? String(evaluations.data.length) : "—"} meta="son başarılı analiz"/>
      <Metric icon="funds" label="Fon hisse akımı" value={formatMoney(latestFlow?.estimated_stock_flow, true)} meta={latestFlow ? `${formatDate(latestFlow.date)} · ${formatPercent(latestFlow.positive_flow_pct)} pozitif` : "veri bekleniyor"} tone={(latestFlow?.estimated_stock_flow ?? 0) >= 0 ? "positive" : "negative"}/>
    </section>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(330px,.75fr)]">
      <div className="space-y-6">
        <section className="panel overflow-hidden"><div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:p-6"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-[12px] bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="spark" size={21}/></div>{focus ? <><div className="min-w-0 flex-1"><div className="mb-2 flex flex-wrap items-center gap-2"><span className="eyebrow">AI gündem özeti</span><span className="pill pill-primary">{eventName(focus.event_type)}</span></div><h2 className="text-lg font-semibold leading-7 tracking-[-0.025em]">{focus.summary}</h2><div className="mt-3 flex items-center gap-3"><TickerPills tickers={focus.ticker_codes}/><span className="text-xs text-[var(--text-muted)]">{relativeTime(focus.created_at)}</span></div></div><ScoreRing score={focus.impact_score} label="Etki"/><Link href={`/analizler/${focus.id}`} className="icon-button shrink-0"><Icon name="arrow"/></Link></> : <div className="flex-1"><p className="eyebrow mb-2">AI gündem özeti</p><h2 className="text-base font-semibold">Değerlendirme akışı hazır</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Gemini değerlendirmeleri çalıştığında en etkili gelişme burada öne çıkarılacak.</p></div>}</div><div className="border-t px-5 py-3 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>AI çıktıları bilgi amaçlıdır; yatırım tavsiyesi veya al-sat sinyali değildir.</div></section>

        <section><SectionTitle title="Güncel haber akışı" subtitle="Bloomberg HT ve Investing kaynaklarından" href="/haberler"/><div className="panel-flat overflow-hidden">{news.data.length ? news.data.map((item, i) => <Link href={`/haberler/${item.id}`} key={item.id} className={`group grid gap-3 p-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[100px_minmax(0,1fr)_auto] sm:items-center ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div><span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{sourceName(item.source)}</span><p className="mt-1 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</p></div><div className="min-w-0"><h3 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.title}</h3><div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>) : <EmptyState compact/>}</div></section>
      </div>

      <div className="space-y-6">
        <section><SectionTitle title="Son KAP bildirimleri" subtitle="Şirket açıklamaları" href="/kap"/><div className="panel-flat overflow-hidden">{disclosures.data.length ? disclosures.data.map((item, i) => <Link href={`/kap/${item.disclosure_index}`} key={item.disclosure_index} className={`block p-4 transition hover:bg-[var(--surface-hover)] ${i ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div className="mb-2 flex items-center justify-between gap-3"><TickerPills tickers={item.ticker_codes}/><span className="shrink-0 text-[11px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</span></div><p className="line-clamp-2 text-sm font-medium leading-5">{item.subject || item.summary || item.kap_title}</p>{item.attachment_count > 0 && <p className="mt-2 flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><Icon name="file" size={12}/>{item.attachment_count} ek dosya</p>}</Link>) : <EmptyState compact/>}</div></section>
        <section><SectionTitle title="Veri kaynakları" subtitle="Sistem bağlantı durumu"/><div className="panel-flat divide-y divide-[var(--border)]">{["KAP bildirim servisi", "Piyasa fiyatları", "Haber kaynakları", "Kurumsal veri"].map((label) => <div key={label} className="flex items-center gap-3 px-4 py-3.5"><span className={`h-2 w-2 rounded-full ${servicesUp ? "bg-[var(--positive)]" : "bg-[var(--warning)]"}`}/><span className="text-xs font-medium">{label}</span><span className="ml-auto text-[11px] text-[var(--text-muted)]">{servicesUp ? "Bağlı" : "Bekleniyor"}</span></div>)}</div></section>
      </div>
    </div>
  </>;
}

function Metric({ icon, label, value, meta, tone }: { icon: "markets" | "news" | "ai" | "funds"; label: string; value: string; meta: string; tone?: "positive" | "negative" }) {
  return <div className="panel-flat p-4 sm:p-5"><div className="mb-5 flex items-center justify-between"><span className="grid h-8 w-8 place-items-center rounded-[9px] bg-[var(--surface-raised)] text-[var(--text-secondary)]"><Icon name={icon} size={16}/></span><Icon name="trend" size={15} className={tone === "negative" ? "text-[var(--negative)]" : "text-[var(--primary)]"}/></div><p className={`text-2xl font-semibold tracking-[-0.035em] ${tone === "positive" ? "text-[var(--positive)]" : tone === "negative" ? "text-[var(--negative)]" : ""}`}>{value}</p><div className="mt-1 flex items-center justify-between gap-2"><span className="text-xs font-medium text-[var(--text-secondary)]">{label}</span><span className="text-[10px] text-[var(--text-muted)]">{meta}</span></div></div>;
}
