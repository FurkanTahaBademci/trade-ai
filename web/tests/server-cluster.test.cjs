const { test } = require("node:test");
const assert = require("node:assert/strict");
const cluster = require("../server-cluster.cjs");

const MB = 1024 * 1024;

test("worker count defaults to 2 and accepts auto", () => {
  assert.equal(cluster.resolveWorkerCount(undefined, 8), cluster.DEFAULT_WORKERS);
  assert.equal(cluster.resolveWorkerCount("", 8), cluster.DEFAULT_WORKERS);
  assert.equal(cluster.resolveWorkerCount("1", 8), 1);
  assert.equal(cluster.resolveWorkerCount(" 3 ", 8), 3);
  assert.equal(cluster.resolveWorkerCount("auto", 6), 6);
  assert.equal(cluster.resolveWorkerCount("AUTO", 64), cluster.MAX_WORKERS);
  assert.equal(cluster.resolveWorkerCount("0", 8), cluster.DEFAULT_WORKERS);
  assert.equal(cluster.resolveWorkerCount("2.5", 8), cluster.DEFAULT_WORKERS);
  assert.equal(cluster.resolveWorkerCount("lots", 8), cluster.DEFAULT_WORKERS);
  assert.equal(cluster.resolveWorkerCount("99", 8), cluster.MAX_WORKERS);
});

test("heap limit splits the container memory limit across workers", () => {
  const total = 16 * 1024 * MB;
  assert.equal(cluster.heapLimitMb(2, 1024 * MB, total), 384);
  assert.equal(cluster.heapLimitMb(4, 1024 * MB, total), 192);
  assert.equal(cluster.heapLimitMb(8, 512 * MB, total), 128);
  // Sınırsız container: Node ya 0 ya da host belleğinden büyük bir değer verir.
  assert.equal(cluster.heapLimitMb(2, 0, total), null);
  assert.equal(cluster.heapLimitMb(2, 2 ** 64, total), null);
});

test("an explicit heap flag is respected", () => {
  assert.equal(cluster.hasHeapFlag("--max-old-space-size=300", []), true);
  assert.equal(cluster.hasHeapFlag("", ["--max-old-space-size=300"]), true);
  assert.equal(cluster.hasHeapFlag("--enable-source-maps", []), false);
});
