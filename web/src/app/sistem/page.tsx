import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { CollectorSchedule, ComponentHealth, SystemHealth } from "@/lib/types";
import { formatDate, relativeTime } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";
import { runScheduleAction, toggleScheduleAction, updateScheduleAction } from "./actions";

export const metadata: Metadata = { title: "Sistem Sağlığı" };

const stateText = {
  healthy: "Sağlıklı",
  stale: "Gecikmiş",
  error: "Hata",
  pending: "İlk çalışma bekleniyor",
};
const scheduleOrder = ["news", "kap", "evaluations", "signals", "prices", "instruments", "fundamentals", "analysts", "institutional_reports", "fund_flows", "tcmb_policy", "paper_portfolio"];

function StatePill({ state }: { state: ComponentHealth["state"] }) {
  const tone = state === "healthy" ? "pill-positive" : state === "error" ? "pill-negative" : "";
  return <span className={`pill ${tone}`}><span className="h-1.5 w-1.5 rounded-full bg-current"/>{stateText[state]}</span>;
}

function ComponentRow({ item }: { item: ComponentHealth }) {
  const age = item.last_success ? relativeTime(item.last_success) : "Henüz başarı kaydı yok";
  return <div className="flex flex-col gap-3 border-t px-4 py-4 first:border-t-0 sm:flex-row sm:items-center" style={{ borderColor: "var(--border)" }}><div className="min-w-0 flex-1"><p className="text-sm font-semibold">{item.label}</p><p className="mt-1 text-[11px] text-[var(--text-muted)]">Son başarılı çalışma: {age}</p></div><StatePill state={item.state}/></div>;
}

export default async function SystemPage({ searchParams }: { searchParams: Promise<{ result?: string; message?: string }> }) {
  const [health, schedules] = await Promise.all([apiGet<SystemHealth | null>("/health/detailed", null), apiGet<CollectorSchedule[]>("/api/schedules", [])]);
  const notice = await searchParams;
  const report = health.data?.monitoring;
  const components = report ? [report.worker, ...Object.values(report.collectors)] : [];
  const healthy = components.filter((item) => item.state === "healthy").length;

  return <><PageHeader eyebrow="Operasyon · Canlı durum" title="Sistem Sağlığı" description="Altyapı bağlantıları, worker heartbeat'i ve veri toplama takvimlerini tek ekrandan yönetin." actions={health.data && <StatePill state={health.data.status === "ok" ? "healthy" : "stale"}/>}/><ServiceNotice show={!health.ok || !schedules.ok}/>
    {notice.message && <div className={`mb-5 rounded-[12px] border px-4 py-3 text-sm ${notice.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: notice.result === "ok" ? "var(--positive)" : "var(--negative)", background: notice.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{notice.message}</div>}
    {!report ? <div className="panel-flat"><EmptyState title="Sağlık verisi alınamadı" description="API ve Redis bağlantısı kurulduğunda bileşen durumları burada görünecek."/></div> : <><div className="mb-6 grid gap-3 sm:grid-cols-3"><Metric label="Sağlıklı bileşen" value={`${healthy}/${components.length}`}/><Metric label="Sorun" value={String(report.problem_count)} tone={report.problem_count === 0}/><Metric label="İlk çalışma bekleyen" value={String(report.pending_count)} tone={report.pending_count === 0}/></div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,.6fr)]"><section><SectionTitle title="Veri hatları" subtitle="Kaynak bazında tazelik ve hata durumu"/><div className="panel-flat overflow-hidden">{components.map((item) => <ComponentRow key={item.name} item={item}/>)}</div></section><aside><SectionTitle title="Altyapı" subtitle="Bağlantı kontrolleri"/><div className="panel-flat overflow-hidden"><Infrastructure label="PostgreSQL" state={health.data?.db}/><Infrastructure label="Redis" state={health.data?.redis}/><div className="border-t p-4 text-[11px] leading-5 text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>Gecikmiş veya hatalı bileşenler, <code>N8N_WEBHOOK_URL</code> tanımlıysa saatlik tekrar sınırıyla webhook'a bildirilir.</div></div></aside></div></>}
    <section className="mt-8"><SectionTitle title="Tarama takvimleri" subtitle="Europe/Istanbul · Ayarlar PostgreSQL'de kalıcıdır"/>{schedules.data.length ? <div className="grid gap-3 lg:grid-cols-2">{[...schedules.data].sort((a, b) => scheduleOrder.indexOf(a.name) - scheduleOrder.indexOf(b.name)).map((item) => <ScheduleCard key={item.name} item={item}/>)}</div> : <div className="panel-flat"><EmptyState title="Takvim bilgisi alınamadı"/></div>}</section>
  </>;
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: boolean }) { return <div className="panel-flat p-5"><p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">{label}</p><p className={`mt-3 text-2xl font-semibold ${tone === true ? "text-[var(--positive)]" : tone === false ? "text-[var(--warning)]" : ""}`}>{value}</p></div>; }
function Infrastructure({ label, state }: { label: string; state?: string }) { const ok = state === "ok"; return <div className="flex items-center gap-3 border-t px-4 py-4 first:border-t-0" style={{ borderColor: "var(--border)" }}><span className={`h-2 w-2 rounded-full ${ok ? "bg-[var(--positive)]" : "bg-[var(--negative)]"}`}/><span className="text-sm font-medium">{label}</span><span className="ml-auto text-xs text-[var(--text-muted)]">{ok ? "Bağlı" : "Hata"}</span></div>; }

function intervalText(minutes: number) { if (minutes % 1440 === 0) return `${minutes / 1440} günde bir`; if (minutes % 60 === 0) return `${minutes / 60} saatte bir`; return `${minutes} dakikada bir`; }
function ScheduleCard({ item }: { item: CollectorSchedule }) { return <article className="panel-flat p-5"><div className="flex items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{item.label}</h3><span className={`pill ${item.enabled ? "pill-positive" : ""}`}>{item.enabled ? "Etkin" : "Duraklatıldı"}</span></div><p className="mt-2 text-xs text-[var(--text-muted)]">{intervalText(item.interval_minutes)} · minimum {item.minimum_interval_minutes} dk</p></div><form action={toggleScheduleAction}><input type="hidden" name="name" value={item.name}/><input type="hidden" name="enabled" value={String(!item.enabled)}/><button className="rounded-[9px] border px-3 py-2 text-xs font-medium transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)" }}>{item.enabled ? "Duraklat" : "Etkinleştir"}</button></form></div><div className="mt-4 grid gap-2 text-[11px] text-[var(--text-muted)] sm:grid-cols-2"><p>Son kuyruğa ekleme<br/><span className="text-[var(--text-secondary)]">{item.last_enqueued_at ? formatDate(item.last_enqueued_at, true) : "Henüz yok"}</span></p><p>Sonraki çalışma<br/><span className="text-[var(--text-secondary)]">{item.next_run_at ? `${formatDate(item.next_run_at, true)} (${relativeTime(item.next_run_at)})` : "Duraklatıldı"}</span></p></div><div className="mt-4 flex flex-col gap-2 border-t pt-4 sm:flex-row" style={{ borderColor: "var(--border)" }}><form action={updateScheduleAction} className="flex min-w-0 flex-1 gap-2"><input type="hidden" name="name" value={item.name}/><input className="input min-w-0" aria-label={`${item.label} tarama aralığı`} type="number" name="interval_minutes" defaultValue={item.interval_minutes} min={item.minimum_interval_minutes} max={43200} required/><button className="shrink-0 rounded-[10px] bg-[var(--primary)] px-3 text-xs font-semibold text-[var(--primary-contrast)]">Dakika kaydet</button></form><form action={runScheduleAction}><input type="hidden" name="name" value={item.name}/><button className="h-10 w-full rounded-[10px] border px-3 text-xs font-semibold transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)" }}>Şimdi çalıştır</button></form></div></article>; }
