import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { ComponentHealth, SystemHealth } from "@/lib/types";
import { relativeTime } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";

export const metadata: Metadata = { title: "Sistem Sağlığı" };

const stateText = {
  healthy: "Sağlıklı",
  stale: "Gecikmiş",
  error: "Hata",
  pending: "İlk çalışma bekleniyor",
};

function StatePill({ state }: { state: ComponentHealth["state"] }) {
  const tone = state === "healthy" ? "pill-positive" : state === "error" ? "pill-negative" : "";
  return <span className={`pill ${tone}`}><span className="h-1.5 w-1.5 rounded-full bg-current"/>{stateText[state]}</span>;
}

function ComponentRow({ item }: { item: ComponentHealth }) {
  const age = item.last_success ? relativeTime(item.last_success) : "Henüz başarı kaydı yok";
  return <div className="flex flex-col gap-3 border-t px-4 py-4 first:border-t-0 sm:flex-row sm:items-center" style={{ borderColor: "var(--border)" }}><div className="min-w-0 flex-1"><p className="text-sm font-semibold">{item.label}</p><p className="mt-1 text-[11px] text-[var(--text-muted)]">Son başarılı çalışma: {age}</p></div><StatePill state={item.state}/></div>;
}

export default async function SystemPage() {
  const health = await apiGet<SystemHealth | null>("/health/detailed", null);
  const report = health.data?.monitoring;
  const components = report ? [report.worker, ...Object.values(report.collectors)] : [];
  const healthy = components.filter((item) => item.state === "healthy").length;

  return <><PageHeader eyebrow="Operasyon · Canlı durum" title="Sistem Sağlığı" description="Altyapı bağlantıları, worker heartbeat'i ve her veri kaynağının son başarılı çalışma zamanı." actions={health.data && <StatePill state={health.data.status === "ok" ? "healthy" : "stale"}/>}/><ServiceNotice show={!health.ok}/>
    {!report ? <div className="panel-flat"><EmptyState title="Sağlık verisi alınamadı" description="API ve Redis bağlantısı kurulduğunda bileşen durumları burada görünecek."/></div> : <><div className="mb-6 grid gap-3 sm:grid-cols-3"><Metric label="Sağlıklı bileşen" value={`${healthy}/${components.length}`}/><Metric label="Sorun" value={String(report.problem_count)} tone={report.problem_count === 0}/><Metric label="İlk çalışma bekleyen" value={String(report.pending_count)} tone={report.pending_count === 0}/></div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,.6fr)]"><section><SectionTitle title="Veri hatları" subtitle="Kaynak bazında tazelik ve hata durumu"/><div className="panel-flat overflow-hidden">{components.map((item) => <ComponentRow key={item.name} item={item}/>)}</div></section><aside><SectionTitle title="Altyapı" subtitle="Bağlantı kontrolleri"/><div className="panel-flat overflow-hidden"><Infrastructure label="PostgreSQL" state={health.data?.db}/><Infrastructure label="Redis" state={health.data?.redis}/><div className="border-t p-4 text-[11px] leading-5 text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>Gecikmiş veya hatalı bileşenler, <code>N8N_WEBHOOK_URL</code> tanımlıysa saatlik tekrar sınırıyla webhook'a bildirilir.</div></div></aside></div></>}
  </>;
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: boolean }) { return <div className="panel-flat p-5"><p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">{label}</p><p className={`mt-3 text-2xl font-semibold ${tone === true ? "text-[var(--positive)]" : tone === false ? "text-[var(--warning)]" : ""}`}>{value}</p></div>; }
function Infrastructure({ label, state }: { label: string; state?: string }) { const ok = state === "ok"; return <div className="flex items-center gap-3 border-t px-4 py-4 first:border-t-0" style={{ borderColor: "var(--border)" }}><span className={`h-2 w-2 rounded-full ${ok ? "bg-[var(--positive)]" : "bg-[var(--negative)]"}`}/><span className="text-sm font-medium">{label}</span><span className="ml-auto text-xs text-[var(--text-muted)]">{ok ? "Bağlı" : "Hata"}</span></div>; }
