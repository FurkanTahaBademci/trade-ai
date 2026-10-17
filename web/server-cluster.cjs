"use strict";

// Next standalone `server.js`'i WEB_WORKERS kadar Node sureciyle calistirir.
// Next SSR tek iş parçacığında render eder; tek süreç tek çekirdekle sınırlı
// kalır. Node cluster ile süreçler aynı 3000 portunu paylaşır (Linux'ta birincil
// süreç bağlantıları sırayla dağıtır).
//
// Süreç belleğinde tutulan durumlar (apiGet yanıt önbelleği, giriş kaba kuvvet
// sayaçları) her süreçte ayrıdır; bkz. docs/CONFIGURATION.md.

const cluster = require("node:cluster");
const os = require("node:os");
const path = require("node:path");
const requestMetrics = require("./request-metrics.cjs");

const DEFAULT_WORKERS = 2;
const MAX_WORKERS = 16;
const SHUTDOWN_TIMEOUT_MS = 15000;
// Bu pencerede bu kadar beklenmedik çıkış olursa birincil süreç de çıkar;
// container yeniden başlatma politikası devreye girer.
const CRASH_WINDOW_MS = 60000;
const MAX_CRASHES = 5;
// Container belleğinin V8 heap'lerine ayrılan payı; kalanı native bellek,
// birincil süreç ve tampon içindir.
const HEAP_SHARE = 0.75;
const MIN_HEAP_MB = 128;

/** "auto" → kullanılabilir çekirdek sayısı; boş/geçersiz → varsayılan. */
function resolveWorkerCount(raw, cpus = os.availableParallelism()) {
  const value = String(raw ?? "").trim().toLowerCase();
  if (!value) return DEFAULT_WORKERS;
  if (value === "auto") return Math.min(Math.max(1, cpus), MAX_WORKERS);
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) return DEFAULT_WORKERS;
  return Math.min(parsed, MAX_WORKERS);
}

/**
 * Container bellek sınırını süreçlere bölerek süreç başına V8 heap sınırı (MB).
 * Node her süreçte heap'i tüm container sınırına göre boyutlar; N süreç
 * birlikte sınırı aşıp OOM kill yemesin diye pay edilir. Sınır yoksa null.
 */
function heapLimitMb(workers, constrained = process.constrainedMemory?.() ?? 0, total = os.totalmem()) {
  if (!constrained || constrained >= total) return null;
  const share = Math.floor((constrained * HEAP_SHARE) / workers / (1024 * 1024));
  return Math.max(MIN_HEAP_MB, share);
}

function hasHeapFlag(nodeOptions = process.env.NODE_OPTIONS ?? "", execArgv = process.execArgv) {
  return /--max-old-space-size/.test(nodeOptions) || execArgv.some((arg) => arg.startsWith("--max-old-space-size"));
}

function startServer() {
  // Ölçüm kancaları (istek/API süresi, süreç CPU'su) Next yüklenmeden kurulmalı.
  requestMetrics.install();
  require(path.join(__dirname, "server.js"));
}

function runPrimary(workers) {
  const heapMb = hasHeapFlag() ? null : heapLimitMb(workers);
  if (heapMb) cluster.setupPrimary({ execArgv: [...process.execArgv, `--max-old-space-size=${heapMb}`] });
  console.log(`[web] ${workers} süreç başlatılıyor${heapMb ? ` (süreç başına heap ${heapMb} MB)` : ""}`);

  requestMetrics.attachPrimary(cluster);
  let shuttingDown = false;
  const crashes = [];
  for (let i = 0; i < workers; i += 1) cluster.fork({ WEB_WORKERS: String(workers) });

  cluster.on("exit", (worker, code, signal) => {
    if (shuttingDown) {
      if (Object.keys(cluster.workers ?? {}).length === 0) process.exit(0);
      return;
    }
    const now = Date.now();
    crashes.push(now);
    while (crashes.length && now - crashes[0] > CRASH_WINDOW_MS) crashes.shift();
    console.error(`[web] süreç ${worker.process.pid} çıktı (kod ${code ?? "-"}, sinyal ${signal ?? "-"})`);
    if (crashes.length >= MAX_CRASHES) {
      console.error(`[web] ${CRASH_WINDOW_MS / 1000} sn içinde ${crashes.length} çıkış; kapanılıyor`);
      process.exit(1);
    }
    cluster.fork({ WEB_WORKERS: String(workers) });
  });

  const shutdown = (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    const alive = Object.values(cluster.workers ?? {});
    if (alive.length === 0) process.exit(0);
    for (const worker of alive) worker?.process.kill(signal);
    setTimeout(() => {
      for (const worker of Object.values(cluster.workers ?? {})) worker?.process.kill("SIGKILL");
      process.exit(0);
    }, SHUTDOWN_TIMEOUT_MS).unref();
  };
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

if (require.main === module) {
  const workers = resolveWorkerCount(process.env.WEB_WORKERS);
  if (workers === 1) {
    process.env.WEB_WORKERS = "1";
    startServer();
  } else if (cluster.isPrimary) {
    runPrimary(workers);
  } else {
    startServer();
  }
}

module.exports = { DEFAULT_WORKERS, MAX_WORKERS, heapLimitMb, hasHeapFlag, resolveWorkerCount };
