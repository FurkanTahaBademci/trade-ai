import { collectWebMetrics } from "@/lib/request-metrics";

// Yük testi sırasında okunmak üzere web süreç/istek ölçümleri. Yalnız yönetici:
// proxy.ts /sistem altını oturum ister. Herkese açık /health'e konmaz.
export const dynamic = "force-dynamic";

export async function GET() {
  const metrics = await collectWebMetrics();
  return Response.json(metrics ?? { enabled: false }, { headers: { "Cache-Control": "no-store" } });
}
