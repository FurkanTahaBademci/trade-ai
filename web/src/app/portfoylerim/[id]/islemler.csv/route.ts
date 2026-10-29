import { apiBase, sessionToken } from "@/lib/account-server";

// Kullanıcının kendi portföyünün işlem dökümü; oturum token'ı API'ye sunucuda iletilir.
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await sessionToken();
  if (!token) return new Response("Giriş gerekli.", { status: 401 });
  if (!/^\d+$/.test(id)) return new Response("Bulunamadı.", { status: 404 });
  try {
    const response = await fetch(`${apiBase()}/api/me/portfolios/${id}/trades.csv`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return new Response("İşlem dökümü alınamadı.", { status: response.status });
    return new Response(response.body, {
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "text/csv; charset=utf-8",
        "Content-Disposition": response.headers.get("content-disposition") ?? `attachment; filename="paper-islemler-${id}.csv"`,
        "Cache-Control": "private, no-store",
      },
    });
  } catch {
    return new Response("Veri servisine ulaşılamadı.", { status: 503 });
  }
}
