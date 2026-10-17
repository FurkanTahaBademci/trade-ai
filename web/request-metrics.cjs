"use strict";

// Web süreçleri için hafif yük ölçümü. server-cluster.cjs, Next sunucusunu
// yüklemeden önce `install()` çağırır:
//   - Her HTTP isteği bir AsyncLocalStorage bağlamında çalışır; istek süresi,
//     API'yi bekleme süresi (uçuştaki API isteklerinin duvar saati birleşimi),
//     API'nin kendi bildirdiği işlem süresi (`Server-Timing: app;dur=`) ve
//     apiGet önbellek sonuçları istek bitince bir halka tampona yazılır.
//   - Süreç CPU'su, event-loop gecikmesi ve host/container CPU bilgisi
//     birkaç saniyede bir örneklenir.
// Sonuçlar yalnız yönetici /sistem sayfasında gösterilir; herkese açık uçlara
// konmaz. Next kodu bu modüle `globalThis[Symbol.for(HOOK_KEY)]` üzerinden
// ulaşır (bkz. src/lib/request-metrics.ts); kanca yoksa (next dev/start) ölçüm
// sessizce kapalıdır.

const { AsyncLocalStorage } = require("node:async_hooks");
const { monitorEventLoopDelay, performance } = require("node:perf_hooks");
const fs = require("node:fs");
const os = require("node:os");

const HOOK_KEY = "trade-ai.request-metrics";
const MAX_SAMPLES = 500;
const SAMPLE_WINDOW_MS = 5 * 60 * 1000;
const TICK_MS = 5000;
// Son dakikadaki en yüksek değerler için tutulan tik sayısı.
const TICK_HISTORY = 12;
const COLLECT_TIMEOUT_MS = 1500;
const MSG = {
  collect: "trade-ai:metrics:collect",
  result: "trade-ai:metrics:result",
  snapshot: "trade-ai:metrics:snapshot",
  snapshotResult: "trade-ai:metrics:snapshot-result",
};
const CACHE_OUTCOMES = ["hit", "shared", "miss", "none"];

/** Ölçülmeyecek istekler için null; kalanlar sayfa/uç grubuna indirgenir. */
function routeKey(url) {
  const pathname = String(url ?? "/").split("?")[0] || "/";
  if (pathname.startsWith("/_next/") || pathname === "/health" || pathname === "/favicon.ico") return null;
  if (/\.[a-z0-9]{2,5}$/i.test(pathname)) return null;
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return "/";
  // /api/list-feed/[kind] gibi web uçları ikinci parçayla anlamlı.
  const keep = parts[0] === "api" ? 2 : 1;
  const head = `/${parts.slice(0, keep).join("/")}`;
  return parts.length > keep ? `${head}/[…]` : head;
}

/** Tam sayfa, istemci gezinmesi (RSC) veya önden yükleme. */
function requestKind(headers = {}) {
  if (headers["next-router-prefetch"]) return "prefetch";
  if (headers.rsc === "1") return "rsc";
  return "doc";
}

/** `Server-Timing` başlığındaki `app;dur=` değeri (ms) ya da null. */
function parseServerTiming(header) {
  if (!header) return null;
  const match = /(?:^|,)\s*app\s*;[^,]*?\bdur=([0-9.]+)/.exec(String(header));
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function createRecorder({ now = () => performance.now(), wallClock = Date.now, maxSamples = MAX_SAMPLES } = {}) {
  const storage = new AsyncLocalStorage();
  const samples = [];
  let inflight = 0;

  function newContext(route, kind) {
    return {
      route, kind, start: now(),
      apiActive: 0, apiSince: 0, apiWallMs: 0, apiSumMs: 0, apiCalls: 0, apiErrors: 0,
      backendMs: 0, backendCalls: 0,
      cache: { hit: 0, shared: 0, miss: 0, none: 0 },
    };
  }

  function record(ctx, status, aborted) {
    const end = now();
    // Yanıt API isteği uçuştayken kapanırsa o ana kadarki bekleme sayılır.
    if (ctx.apiActive > 0) ctx.apiWallMs += end - ctx.apiSince;
    samples.push({
      at: wallClock(), route: ctx.route, kind: ctx.kind, status, aborted,
      totalMs: round(end - ctx.start), apiWallMs: round(ctx.apiWallMs), apiSumMs: round(ctx.apiSumMs),
      apiCalls: ctx.apiCalls, apiErrors: ctx.apiErrors, backendMs: round(ctx.backendMs), backendCalls: ctx.backendCalls,
      cache: { ...ctx.cache },
    });
    if (samples.length > maxSamples) samples.splice(0, samples.length - maxSamples);
  }

  /** http.createServer dinleyicisini ölçüm bağlamıyla sarar. */
  function wrapListener(listener) {
    return function measuredListener(req, res) {
      const route = routeKey(req.url);
      if (!route) return listener.call(this, req, res);
      const ctx = newContext(route, requestKind(req.headers));
      inflight += 1;
      res.once("close", () => {
        inflight -= 1;
        record(ctx, res.statusCode, !res.writableFinished);
      });
      return storage.run(ctx, () => listener.call(this, req, res));
    };
  }

  /**
   * Bir API beklemesi başlatır; dönen fonksiyon beklemeyi bitirir. Eşzamanlı
   * beklemeler duvar saatinde bir kez sayılır (apiWallMs); `call` olanlar
   * ayrıca tek tek toplanır (apiSumMs).
   */
  function apiStart() {
    const ctx = storage.getStore();
    if (!ctx) return () => {};
    const started = now();
    if (ctx.apiActive === 0) ctx.apiSince = started;
    ctx.apiActive += 1;
    let done = false;
    return ({ call = false, error = false, backendMs = null } = {}) => {
      if (done) return;
      done = true;
      const ended = now();
      ctx.apiActive -= 1;
      if (ctx.apiActive === 0) ctx.apiWallMs += ended - ctx.apiSince;
      if (call) {
        ctx.apiCalls += 1;
        ctx.apiSumMs += ended - started;
        if (error) ctx.apiErrors += 1;
      }
      if (typeof backendMs === "number") {
        ctx.backendMs += backendMs;
        ctx.backendCalls += 1;
      }
    };
  }

  function cacheOutcome(outcome) {
    const ctx = storage.getStore();
    if (ctx && CACHE_OUTCOMES.includes(outcome)) ctx.cache[outcome] += 1;
  }

  /** API adresine giden fetch'leri ölçen sarmalayıcı. */
  function wrapFetch(originalFetch, apiBase) {
    const prefix = String(apiBase).replace(/\/+$/, "");
    return function measuredFetch(input, init) {
      const url = typeof input === "string" ? input : input?.url ?? String(input);
      if (!url.startsWith(prefix) || !storage.getStore()) return originalFetch(input, init);
      const end = apiStart();
      return originalFetch(input, init).then(
        (response) => {
          end({ call: true, error: !response.ok, backendMs: parseServerTiming(response.headers?.get?.("server-timing")) });
          return response;
        },
        (error) => {
          end({ call: true, error: true });
          throw error;
        },
      );
    };
  }

  return {
    wrapListener, wrapFetch, apiStart, cacheOutcome,
    samples: () => samples.slice(),
    inflight: () => inflight,
  };
}

function round(value) {
  return Math.round(value * 10) / 10;
}

// --- Süreç ve host örneklemesi -------------------------------------------

function readFile(path) {
  try {
    return fs.readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

/** Container'a tanınan CPU kotası (çekirdek) ya da sınırsızsa null. cgroup v2, yoksa v1. */
function cgroupCpuQuota(read = readFile) {
  const v2 = read("/sys/fs/cgroup/cpu.max");
  if (v2) {
    const [quota, period] = v2.trim().split(/\s+/);
    if (quota === "max") return null;
    const value = Number(quota) / Number(period);
    return Number.isFinite(value) && value > 0 ? round(value * 10) / 10 : null;
  }
  const quota = Number(read("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"));
  const period = Number(read("/sys/fs/cgroup/cpu/cpu.cfs_period_us"));
  if (!(quota > 0) || !(period > 0)) return null;
  return round((quota / period) * 10) / 10;
}

/** Container'ın toplam CPU kullanımı ve kısılma sayaçları (µs). */
function cgroupCpuStat(read = readFile) {
  const text = read("/sys/fs/cgroup/cpu.stat");
  if (!text) return null;
  const values = {};
  for (const line of text.split("\n")) {
    const [key, raw] = line.trim().split(/\s+/);
    if (key) values[key] = Number(raw);
  }
  if (!Number.isFinite(values.usage_usec)) return null;
  return { usageUs: values.usage_usec, throttledUs: values.throttled_usec ?? 0, nrThrottled: values.nr_throttled ?? 0, nrPeriods: values.nr_periods ?? 0 };
}

/** /proc/stat: host geneli CPU sayaçları (container ad alanında da host'u gösterir). */
function hostCpuStat(read = readFile) {
  const text = read("/proc/stat");
  if (!text) return null;
  const line = text.split("\n").find((item) => item.startsWith("cpu "));
  const running = /^procs_running\s+(\d+)/m.exec(text);
  if (!line) return null;
  const [user, nice, system, idle, iowait = 0, irq = 0, softirq = 0, steal = 0] = line.trim().split(/\s+/).slice(1).map(Number);
  const total = user + nice + system + idle + iowait + irq + softirq + steal;
  return { total, idle: idle + iowait, steal, procsRunning: running ? Number(running[1]) : null };
}

function percent(part, whole) {
  return whole > 0 ? round((part / whole) * 100) : null;
}

/** İki host sayacı okuması arasındaki meşgul ve çalınan (steal) CPU yüzdesi. */
function hostCpuDelta(previous, current) {
  if (!previous || !current) return null;
  const total = current.total - previous.total;
  if (total <= 0) return null;
  return {
    busyPercent: percent(total - (current.idle - previous.idle), total),
    stealPercent: percent(current.steal - previous.steal, total),
  };
}

function createProcessSampler({ read = readFile, tickMs = TICK_MS } = {}) {
  // Histogram zamanlayıcı aralığını da içerir (boşta ≈ çözünürlük); yalnız
  // aşan gecikme raporlanır.
  const resolutionMs = 10;
  const loop = monitorEventLoopDelay({ resolution: resolutionMs });
  loop.enable();
  let lastAt = performance.now();
  let lastCpu = process.cpuUsage();
  let lastHost = hostCpuStat(read);
  let lastCgroup = cgroupCpuStat(read);
  let current = null;
  const history = [];

  function tick() {
    const at = performance.now();
    const elapsedUs = (at - lastAt) * 1000;
    const cpu = process.cpuUsage(lastCpu);
    const host = hostCpuStat(read);
    const cgroup = cgroupCpuStat(read);
    const ms = (ns) => round(Math.max(0, ns / 1e6 - resolutionMs));
    current = {
      windowS: round(elapsedUs / 1e6),
      cpuPercent: percent(cpu.user + cpu.system, elapsedUs),
      eventLoop: { p50Ms: ms(loop.percentile(50)), p99Ms: ms(loop.percentile(99)), maxMs: ms(loop.max) },
      host: { ...hostCpuDelta(lastHost, host), procsRunning: host?.procsRunning ?? null },
      container: cgroup && lastCgroup ? {
        cpuPercent: percent(cgroup.usageUs - lastCgroup.usageUs, elapsedUs),
        throttledPercent: percent(cgroup.nrThrottled - lastCgroup.nrThrottled, cgroup.nrPeriods - lastCgroup.nrPeriods),
        throttledMs: round((cgroup.throttledUs - lastCgroup.throttledUs) / 1000),
      } : null,
    };
    history.push({ cpuPercent: current.cpuPercent, loopP99Ms: current.eventLoop.p99Ms, hostBusyPercent: current.host.busyPercent ?? null });
    if (history.length > TICK_HISTORY) history.shift();
    loop.reset();
    lastAt = at;
    lastCpu = process.cpuUsage();
    lastHost = host;
    lastCgroup = cgroup;
  }

  const timer = setInterval(tick, tickMs);
  timer.unref();

  function peak(key) {
    const values = history.map((item) => item[key]).filter((value) => typeof value === "number");
    return values.length ? Math.max(...values) : null;
  }

  return {
    stop() { clearInterval(timer); loop.disable(); },
    tick,
    snapshot() {
      const memory = process.memoryUsage();
      return {
        current,
        peak1m: { cpuPercent: peak("cpuPercent"), loopP99Ms: peak("loopP99Ms"), hostBusyPercent: peak("hostBusyPercent") },
        rssMb: Math.round(memory.rss / 1048576),
        heapUsedMb: Math.round(memory.heapUsed / 1048576),
      };
    },
  };
}

/** Host ve container'ın gördüğü CPU/bellek bilgisi (anlık). */
function hostInfo(read = readFile) {
  return {
    loadavg: os.loadavg().map((value) => round(value * 100) / 100),
    hostCpus: os.cpus().length,
    availableCpus: os.availableParallelism(),
    cpuQuota: cgroupCpuQuota(read),
    memoryTotalMb: Math.round(os.totalmem() / 1048576),
    memoryFreeMb: Math.round(os.freemem() / 1048576),
    containerMemoryLimitMb: (() => {
      const limit = process.constrainedMemory?.() ?? 0;
      return limit && limit < os.totalmem() ? Math.round(limit / 1048576) : null;
    })(),
  };
}

// --- Özetleme --------------------------------------------------------------

function quantile(sorted, q) {
  if (sorted.length === 0) return null;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1));
  return sorted[index];
}

function stats(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  return { p50: quantile(sorted, 0.5), p95: quantile(sorted, 0.95), max: sorted.length ? sorted[sorted.length - 1] : null };
}

/**
 * Örnekleri sayfa/istek türüne göre özetler. "render" = toplam süre − API
 * bekleme süresi: sunucu tarafı render, JSON ayrıştırma, event-loop kuyruğu ve
 * yanıtın gönderilmesi.
 */
function summarize(samples, { nowMs = Date.now(), windowMs = SAMPLE_WINDOW_MS } = {}) {
  const recent = samples.filter((sample) => nowMs - sample.at <= windowMs);
  const spanS = recent.length ? Math.max(1, (nowMs - Math.min(...recent.map((sample) => sample.at))) / 1000) : 0;
  const groups = new Map();
  for (const sample of recent) {
    const key = `${sample.kind} ${sample.route}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(sample);
  }
  const summarizeGroup = (items) => {
    const cache = { hit: 0, shared: 0, miss: 0, none: 0 };
    for (const item of items) for (const key of CACHE_OUTCOMES) cache[key] += item.cache?.[key] ?? 0;
    const backend = items.filter((item) => item.backendCalls > 0);
    return {
      count: items.length,
      perSecond: spanS ? round(items.length / spanS) : 0,
      errors: items.filter((item) => item.status >= 500).length,
      aborted: items.filter((item) => item.aborted).length,
      totalMs: stats(items.map((item) => item.totalMs)),
      apiWaitMs: stats(items.map((item) => item.apiWallMs)),
      renderMs: stats(items.map((item) => round(Math.max(0, item.totalMs - item.apiWallMs)))),
      // Tek tek API çağrıları ve API'nin kendi bildirdiği işlem süresi (ortalama).
      apiCallsAvg: round(items.reduce((sum, item) => sum + item.apiCalls, 0) / items.length),
      apiCallMsAvg: avgPerCall(items, "apiSumMs", "apiCalls"),
      backendMsAvg: avgPerCall(backend, "backendMs", "backendCalls"),
      cache,
    };
  };
  const routes = [...groups.entries()]
    .map(([key, items]) => ({ route: items[0].route, kind: items[0].kind, key, ...summarizeGroup(items) }))
    .sort((a, b) => b.count - a.count);
  return { windowS: round(spanS), overall: recent.length ? summarizeGroup(recent) : null, routes };
}

function avgPerCall(items, sumKey, countKey) {
  const calls = items.reduce((sum, item) => sum + item[countKey], 0);
  if (!calls) return null;
  return round(items.reduce((sum, item) => sum + item[sumKey], 0) / calls);
}

// --- Kurulum ve süreçler arası toplama -----------------------------------

let installed = null;

function localProcessSnapshot() {
  return {
    pid: process.pid,
    uptimeS: Math.round(process.uptime()),
    inflight: installed.recorder.inflight(),
    ...installed.sampler.snapshot(),
    samples: installed.recorder.samples(),
  };
}

/**
 * Bu süreçte ölçümü kurar: http.createServer dinleyicisini ve global fetch'i
 * sarar, kancayı globalThis'e koyar. Next yüklenmeden önce çağrılmalı.
 */
function install({ apiBase = process.env.API_INTERNAL_URL ?? "http://localhost:8000" } = {}) {
  if (installed) return installed;
  const http = require("node:http");
  const recorder = createRecorder();
  const sampler = createProcessSampler();
  installed = { recorder, sampler };

  const originalCreateServer = http.createServer;
  http.createServer = function createMeasuredServer(...args) {
    const index = args.findIndex((arg) => typeof arg === "function");
    if (index >= 0) args[index] = recorder.wrapListener(args[index]);
    return originalCreateServer.apply(this, args);
  };
  if (typeof globalThis.fetch === "function") globalThis.fetch = recorder.wrapFetch(globalThis.fetch.bind(globalThis), apiBase);

  const pending = new Map();
  let nextId = 0;
  const cluster = require("node:cluster");
  if (cluster.isWorker && process.send) {
    process.on("message", (message) => {
      if (message?.type === MSG.snapshot) {
        process.send({ type: MSG.snapshotResult, id: message.id, snapshot: localProcessSnapshot() });
      } else if (message?.type === MSG.result && pending.has(message.id)) {
        pending.get(message.id)(message.processes);
        pending.delete(message.id);
      }
    });
  }

  /** Tüm web süreçlerinin anlık görüntüsü; birincil süreç yanıt vermezse yalnız bu süreç. */
  function collectProcesses() {
    if (!cluster.isWorker || !process.send) return Promise.resolve([localProcessSnapshot()]);
    const id = `${process.pid}-${(nextId += 1)}`;
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        resolve([localProcessSnapshot()]);
      }, COLLECT_TIMEOUT_MS);
      pending.set(id, (processes) => {
        clearTimeout(timer);
        resolve(processes);
      });
      process.send({ type: MSG.collect, id });
    });
  }

  async function collect() {
    const processes = await collectProcesses();
    const samples = processes.flatMap((item) => item.samples ?? []);
    return {
      collectedAt: new Date().toISOString(),
      host: hostInfo(),
      processes: processes.map(({ samples: _samples, ...rest }) => rest).sort((a, b) => a.pid - b.pid),
      requests: summarize(samples),
    };
  }

  globalThis[Symbol.for(HOOK_KEY)] = {
    apiStart: recorder.apiStart,
    cacheOutcome: recorder.cacheOutcome,
    collect,
  };
  return installed;
}

/** Birincil süreç: bir işçinin toplama isteğini tüm işçilere dağıtıp yanıtları birleştirir. */
function attachPrimary(cluster) {
  const rounds = new Map();
  const finish = (id) => {
    const state = rounds.get(id);
    if (!state) return;
    rounds.delete(id);
    clearTimeout(state.timer);
    if (state.requester.isConnected()) state.requester.send({ type: MSG.result, id, processes: state.snapshots });
  };
  cluster.on("message", (worker, message) => {
    if (message?.type === MSG.collect) {
      const workers = Object.values(cluster.workers ?? {}).filter((item) => item?.isConnected());
      const state = { requester: worker, expected: workers.length, snapshots: [], timer: setTimeout(() => finish(message.id), COLLECT_TIMEOUT_MS - 300) };
      rounds.set(message.id, state);
      for (const item of workers) item.send({ type: MSG.snapshot, id: message.id });
    } else if (message?.type === MSG.snapshotResult) {
      const state = rounds.get(message.id);
      if (!state) return;
      state.snapshots.push(message.snapshot);
      if (state.snapshots.length >= state.expected) finish(message.id);
    }
  });
}

module.exports = {
  HOOK_KEY, MSG,
  attachPrimary, cgroupCpuQuota, cgroupCpuStat, createProcessSampler, createRecorder, hostCpuDelta, hostCpuStat,
  hostInfo, install, parseServerTiming, requestKind, routeKey, summarize,
};
