// web/request-metrics.cjs'in globalThis'e koyduğu ölçüm kancasına erişim.
// Kanca yalnız server-cluster.cjs ile çalışırken (Docker imajı) vardır;
// `next dev`/`next start` altında ölçüm kapalıdır ve bu fonksiyonlar no-op olur.

export type ApiCacheOutcome = "hit" | "shared" | "miss" | "none";

type Stats = { p50: number | null; p95: number | null; max: number | null };

export type RequestGroupSummary = {
  count: number;
  perSecond: number;
  errors: number;
  aborted: number;
  totalMs: Stats;
  apiWaitMs: Stats;
  renderMs: Stats;
  apiCallsAvg: number;
  apiCallMsAvg: number | null;
  backendMsAvg: number | null;
  cache: Record<ApiCacheOutcome, number>;
};

export type ProcessMetrics = {
  pid: number;
  uptimeS: number;
  inflight: number;
  rssMb: number;
  heapUsedMb: number;
  current: null | {
    windowS: number;
    cpuPercent: number | null;
    eventLoop: { p50Ms: number; p99Ms: number; maxMs: number };
    host: { busyPercent?: number | null; stealPercent?: number | null; procsRunning: number | null };
    container: null | { cpuPercent: number | null; throttledPercent: number | null; throttledMs: number };
  };
  peak1m: { cpuPercent: number | null; loopP99Ms: number | null; hostBusyPercent: number | null };
};

export type WebMetrics = {
  collectedAt: string;
  host: {
    loadavg: number[];
    hostCpus: number;
    availableCpus: number;
    cpuQuota: number | null;
    memoryTotalMb: number;
    memoryFreeMb: number;
    containerMemoryLimitMb: number | null;
  };
  processes: ProcessMetrics[];
  requests: {
    windowS: number;
    overall: RequestGroupSummary | null;
    routes: (RequestGroupSummary & { route: string; kind: "doc" | "rsc" | "prefetch"; key: string })[];
  };
};

type Hook = {
  apiStart: () => (info?: { call?: boolean }) => void;
  cacheOutcome: (outcome: ApiCacheOutcome) => void;
  collect: () => Promise<WebMetrics>;
};

const HOOK_KEY = Symbol.for("trade-ai.request-metrics");

function hook(): Hook | undefined {
  return (globalThis as { [HOOK_KEY]?: Hook })[HOOK_KEY];
}

/** Önbellekteki uçuştaki bir isteği beklemek de API beklemesidir; çağrı sayılmaz. */
export function startApiWait(): () => void {
  const end = hook()?.apiStart();
  return () => end?.();
}

export function recordCacheOutcome(outcome: ApiCacheOutcome) {
  hook()?.cacheOutcome(outcome);
}

/** Tüm web süreçlerinin ölçümleri; ölçüm kapalıysa null. */
export async function collectWebMetrics(): Promise<WebMetrics | null> {
  const current = hook();
  if (!current) return null;
  try {
    return await current.collect();
  } catch {
    return null;
  }
}
