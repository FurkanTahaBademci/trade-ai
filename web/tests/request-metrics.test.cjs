const { test } = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const metrics = require("../request-metrics.cjs");

test("routes are grouped by page and static assets are skipped", () => {
  assert.equal(metrics.routeKey("/"), "/");
  assert.equal(metrics.routeKey("/piyasalar?sort=ticker"), "/piyasalar");
  assert.equal(metrics.routeKey("/hisse/THYAO"), "/hisse/[…]");
  assert.equal(metrics.routeKey("/api/market-feed"), "/api/market-feed");
  assert.equal(metrics.routeKey("/api/list-feed/kap?page=2"), "/api/list-feed/[…]");
  assert.equal(metrics.routeKey("/_next/static/chunks/a.js"), null);
  assert.equal(metrics.routeKey("/health"), null);
  assert.equal(metrics.routeKey("/icon.svg"), null);
  assert.equal(metrics.requestKind({}), "doc");
  assert.equal(metrics.requestKind({ rsc: "1" }), "rsc");
  assert.equal(metrics.requestKind({ rsc: "1", "next-router-prefetch": "1" }), "prefetch");
});

test("Server-Timing app duration is parsed", () => {
  assert.equal(metrics.parseServerTiming("app;dur=12.5"), 12.5);
  assert.equal(metrics.parseServerTiming('db;dur=3, app;desc="api";dur=40'), 40);
  assert.equal(metrics.parseServerTiming("db;dur=3"), null);
  assert.equal(metrics.parseServerTiming(null), null);
});

function fakeClock() {
  let value = 0;
  return { now: () => value, advance: (ms) => { value += ms; } };
}

function fakeResponse() {
  const res = new EventEmitter();
  res.statusCode = 200;
  res.writableFinished = true;
  return res;
}

test("a request records API wait as the wall-clock union of concurrent calls", async () => {
  const clock = fakeClock();
  const recorder = metrics.createRecorder({ now: clock.now, wallClock: () => 1000 });
  const res = fakeResponse();
  const listener = recorder.wrapListener(() => {
    clock.advance(5);
    const a = recorder.apiStart();
    clock.advance(10);
    const b = recorder.apiStart();
    clock.advance(30);
    a({ call: true, backendMs: 20 });
    clock.advance(10);
    b({ call: true, error: true });
    recorder.cacheOutcome("hit");
    clock.advance(25);
  });
  listener({ url: "/piyasalar", headers: {} }, res);
  assert.equal(recorder.inflight(), 1);
  res.emit("close");
  const [sample] = recorder.samples();
  assert.equal(recorder.inflight(), 0);
  assert.equal(sample.route, "/piyasalar");
  assert.equal(sample.totalMs, 80);
  assert.equal(sample.apiWallMs, 50);
  assert.equal(sample.apiSumMs, 80);
  assert.equal(sample.apiCalls, 2);
  assert.equal(sample.apiErrors, 1);
  assert.equal(sample.backendMs, 20);
  assert.equal(sample.cache.hit, 1);
});

test("measurement is a no-op outside a request and for skipped paths", () => {
  const recorder = metrics.createRecorder();
  recorder.apiStart()({ call: true });
  recorder.cacheOutcome("miss");
  const res = fakeResponse();
  recorder.wrapListener(() => {})({ url: "/_next/static/x.js", headers: {} }, res);
  res.emit("close");
  assert.equal(recorder.samples().length, 0);
});

test("fetch wrapper only measures calls to the API base", async () => {
  const recorder = metrics.createRecorder();
  const seen = [];
  const fetch = recorder.wrapFetch(async (url) => {
    seen.push(url);
    return { ok: true, headers: { get: () => "app;dur=7" } };
  }, "http://api:8000/");
  const res = fakeResponse();
  await new Promise((resolve) => {
    recorder.wrapListener(async () => {
      await fetch("http://api:8000/api/news");
      await fetch("https://example.test/x");
      resolve();
    })({ url: "/haberler", headers: {} }, res);
  });
  res.emit("close");
  const [sample] = recorder.samples();
  assert.equal(seen.length, 2);
  assert.equal(sample.apiCalls, 1);
  assert.equal(sample.backendMs, 7);
});

test("the sample buffer is bounded", () => {
  const recorder = metrics.createRecorder({ maxSamples: 3 });
  for (let i = 0; i < 5; i += 1) {
    const res = fakeResponse();
    recorder.wrapListener(() => {})({ url: `/p${i}`, headers: {} }, res);
    res.emit("close");
  }
  assert.deepEqual(recorder.samples().map((item) => item.route), ["/p2", "/p3", "/p4"]);
});

test("summary splits total time into API wait and render per page", () => {
  const sample = (route, totalMs, apiWallMs, extra = {}) => ({
    at: 100_000, route, kind: "doc", status: 200, aborted: false, totalMs, apiWallMs, apiSumMs: apiWallMs,
    apiCalls: 1, apiErrors: 0, backendMs: 0, backendCalls: 0, cache: { hit: 0, shared: 0, miss: 1, none: 0 }, ...extra,
  });
  const summary = metrics.summarize([
    sample("/", 100, 60, { backendMs: 20, backendCalls: 1 }),
    sample("/", 300, 100, { status: 503 }),
    sample("/kap", 50, 10),
    { ...sample("/", 999, 999), at: 0 },
  ], { nowMs: 110_000, windowMs: 60_000 });
  assert.equal(summary.windowS, 10);
  assert.equal(summary.overall.count, 3);
  const home = summary.routes[0];
  assert.equal(home.route, "/");
  assert.equal(home.count, 2);
  assert.equal(home.perSecond, 0.2);
  assert.equal(home.errors, 1);
  assert.deepEqual(home.totalMs, { p50: 100, p95: 300, max: 300 });
  assert.deepEqual(home.apiWaitMs, { p50: 60, p95: 100, max: 100 });
  assert.deepEqual(home.renderMs, { p50: 40, p95: 200, max: 200 });
  assert.equal(home.backendMsAvg, 20);
  assert.equal(home.cache.miss, 2);
  assert.equal(metrics.summarize([]).overall, null);
});

test("cgroup and /proc readers parse container quota and host counters", () => {
  const files = {
    "/sys/fs/cgroup/cpu.max": "150000 100000\n",
    "/sys/fs/cgroup/cpu.stat": "usage_usec 5000\nnr_periods 10\nnr_throttled 2\nthrottled_usec 300\n",
    "/proc/stat": "cpu  100 0 50 800 50 0 0 0 0 0\ncpu0 1 2 3 4\nprocs_running 6\n",
  };
  const read = (path) => files[path] ?? null;
  assert.equal(metrics.cgroupCpuQuota(read), 1.5);
  assert.equal(metrics.cgroupCpuQuota((path) => (path.endsWith("cpu.max") ? "max 100000" : null)), null);
  assert.equal(metrics.cgroupCpuQuota(() => null), null);
  assert.deepEqual(metrics.cgroupCpuStat(read), { usageUs: 5000, throttledUs: 300, nrThrottled: 2, nrPeriods: 10 });
  const host = metrics.hostCpuStat(read);
  assert.deepEqual(host, { total: 1000, idle: 850, steal: 0, procsRunning: 6 });
  const later = { total: 2000, idle: 1350, steal: 100, procsRunning: 4 };
  assert.deepEqual(metrics.hostCpuDelta(host, later), { busyPercent: 50, stealPercent: 10 });
  assert.equal(metrics.hostCpuDelta(null, later), null);
});

test("process sampler reports CPU and event-loop delay", () => {
  const sampler = metrics.createProcessSampler({ read: () => null, tickMs: 60_000 });
  try {
    const start = Date.now();
    while (Date.now() - start < 20) { /* CPU harca */ }
    sampler.tick();
    const snapshot = sampler.snapshot();
    assert.ok(snapshot.current.cpuPercent > 0);
    assert.equal(typeof snapshot.current.eventLoop.p99Ms, "number");
    assert.equal(snapshot.current.container, null);
    assert.ok(snapshot.rssMb > 0);
  } finally {
    sampler.stop();
  }
});
