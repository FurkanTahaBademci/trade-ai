import { DataMetric as Metric, EmptyState } from "@/components/ui";
import type { RequestGroupSummary, WebMetrics } from "@/lib/request-metrics";

const kindText = { doc: "Sayfa", rsc: "Gezinme", prefetch: "Önden yükleme" } as const;

function ms(value: number | null | undefined) {
  if (value == null) return "—";
  return value >= 1000 ? `${(value / 1000).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} sn` : `${Math.round(value).toLocaleString("tr-TR")} ms`;
}

function pct(value: number | null | undefined) {
  return value == null ? "—" : `%${value.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;
}

function pair(stats: RequestGroupSummary["totalMs"]) {
  return `${ms(stats.p50)} / ${ms(stats.p95)}`;
}

function cacheText(cache: RequestGroupSummary["cache"]) {
  const parts = [cache.hit && `${cache.hit} isabet`, cache.shared && `${cache.shared} ortak`, cache.miss && `${cache.miss} ıska`, cache.none && `${cache.none} önbelleksiz`].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

export function WebLoadPanel({ metrics }: { metrics: WebMetrics | null }) {
  if (!metrics) {
    return <div className="panel-flat"><EmptyState title="Web ölçümü kapalı" description="İstek ve süreç ölçümü yalnız Docker imajındaki server-cluster.cjs ile çalışırken toplanır (next dev/start altında kapalıdır)."/></div>;
  }
  const { host, processes, requests } = metrics;
  const hostBusy = processes.map((item) => item.current?.host.busyPercent).find((value) => value != null);
  const steal = processes.map((item) => item.current?.host.stealPercent).find((value) => value != null);
  const running = processes.map((item) => item.current?.host.procsRunning).find((value) => value != null);
  const container = processes.map((item) => item.current?.container).find(Boolean);
  const peakBusy = Math.max(...processes.map((item) => item.peak1m.hostBusyPercent ?? -1));
  const overall = requests.overall;
  return <>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Host yükü (1 · 5 · 15 dk)" value={host.loadavg.map((value) => value.toLocaleString("tr-TR")).join(" · ")} meta={`Çalışmaya hazır iş: ${running ?? "—"}`}/>
      <Metric label="CPU (host · görünen · kota)" value={`${host.hostCpus} · ${host.availableCpus} · ${host.cpuQuota ?? "sınırsız"}`} meta={`Bellek boş ${host.memoryFreeMb.toLocaleString("tr-TR")} / ${host.memoryTotalMb.toLocaleString("tr-TR")} MB`}/>
      <Metric label="Host CPU meşgul" value={pct(hostBusy)} tone={hostBusy != null && hostBusy >= 90 ? "warning" : undefined} meta={`1 dk tepe ${pct(peakBusy >= 0 ? peakBusy : null)} · steal ${pct(steal)}`}/>
      <Metric label="Web container CPU" value={container ? `${pct(container.cpuPercent)}` : "—"} meta={container ? `Kısılan dönem ${pct(container.throttledPercent)} (${ms(container.throttledMs)})` : "cgroup sayacı okunamadı"}/>
    </div>
    <div className="table-shell mt-3 overflow-x-auto"><table className="data-table min-w-[720px]"><caption>Web süreçleri · CPU %100 = bir çekirdek; event-loop gecikmesi yüksekse süreç CPU'ya doymuştur</caption><thead><tr><th>PID</th><th className="text-right">CPU (anlık · 1 dk tepe)</th><th className="text-right">Event-loop p50 · p99 · en çok</th><th className="text-right">Süren istek</th><th className="text-right">Bellek (RSS · heap)</th><th className="text-right">Çalışma</th></tr></thead><tbody>
      {processes.map((item) => <tr key={item.pid} className="whitespace-nowrap"><td className="terminal-mono">{item.pid}</td><td className="text-right">{pct(item.current?.cpuPercent)} · {pct(item.peak1m.cpuPercent)}</td><td className="text-right">{item.current ? `${ms(item.current.eventLoop.p50Ms)} · ${ms(item.current.eventLoop.p99Ms)} · ${ms(item.current.eventLoop.maxMs)}` : "—"}</td><td className="text-right">{item.inflight}</td><td className="text-right">{item.rssMb} · {item.heapUsedMb} MB</td><td className="text-right">{Math.round(item.uptimeS / 60).toLocaleString("tr-TR")} dk</td></tr>)}
    </tbody></table></div>
    {overall ? <div className="table-shell mt-3 overflow-x-auto"><table className="data-table min-w-[960px]"><caption>Son {Math.round(requests.windowS).toLocaleString("tr-TR")} sn · {overall.count.toLocaleString("tr-TR")} istek ({overall.perSecond.toLocaleString("tr-TR")}/sn) · süreler p50 / p95 · render = toplam − API bekleme</caption><thead><tr><th>Sayfa</th><th className="text-right">İstek</th><th className="text-right">Toplam</th><th className="text-right">API bekleme</th><th className="text-right">Render</th><th className="text-right" title="İstek başına API çağrısı · çağrı başına web'in ölçtüğü süre · API'nin kendi bildirdiği işlem süresi">API çağrı · süre · işlem</th><th>Önbellek</th><th className="text-right">5xx</th></tr></thead><tbody>
      <Row label="Tümü" item={overall} strong/>
      {requests.routes.map((item) => <Row key={item.key} label={<>{item.route}{item.kind !== "doc" && <span className="pill ml-1.5">{kindText[item.kind]}</span>}</>} item={item}/>)}
    </tbody></table></div> : <div className="panel-flat mt-3"><EmptyState title="Henüz ölçülmüş istek yok"/></div>}
    <p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">API bekleme, sayfa için uçuştaki API isteklerinin duvar saati toplamıdır (yanıt başlıkları gelene kadar). API işlem süresi API'nin <code>Server-Timing</code> başlığından gelir; çağrı süresiyle arasındaki fark ağ, uvicorn kuyruğu ve event-loop beklemesidir. Ölçümler süreç belleğindedir; süreç başına son 500 istek tutulur. JSON: <code>/sistem/metrikler</code>.</p>
  </>;
}

function Row({ label, item, strong }: { label: React.ReactNode; item: RequestGroupSummary; strong?: boolean }) {
  return <tr className={`whitespace-nowrap ${strong ? "font-semibold" : ""}`}><td className="terminal-mono">{label}</td><td className="text-right">{item.count.toLocaleString("tr-TR")} <span className="text-[var(--text-muted)]">({item.perSecond.toLocaleString("tr-TR")}/sn)</span></td><td className="text-right">{pair(item.totalMs)}</td><td className="text-right">{pair(item.apiWaitMs)}</td><td className="text-right">{pair(item.renderMs)}</td><td className="text-right">{item.apiCallsAvg.toLocaleString("tr-TR")} · {ms(item.apiCallMsAvg)} · {ms(item.backendMsAvg)}</td><td className="text-[var(--text-secondary)]">{cacheText(item.cache)}</td><td className={`text-right ${item.errors ? "text-[var(--negative)]" : ""}`}>{item.errors}</td></tr>;
}
