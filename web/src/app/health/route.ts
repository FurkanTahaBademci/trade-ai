import { APP_COMMIT, APP_VERSION } from "@/lib/build-info";

// WEB_WORKERS çalışma anında server-cluster.cjs tarafından verilir; build'de
// sabitlenmesin.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({
    status: "ok",
    service: "web",
    version: APP_VERSION,
    commit: APP_COMMIT || null,
    workers: Number(process.env.WEB_WORKERS) || 1,
  });
}
