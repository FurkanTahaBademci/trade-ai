import type { NextRequest } from "next/server";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ disclosureIndex: string; objId: string }> },
) {
  const { disclosureIndex, objId } = await params;
  if (!/^\d+$/.test(disclosureIndex) || !/^[a-f0-9]{16,64}$/i.test(objId)) {
    return Response.json({ detail: "Gecersiz ek dosya kimligi" }, { status: 400 });
  }
  try {
    const upstream = await fetch(
      `${apiBase()}/api/disclosures/${disclosureIndex}/attachments/${objId}`,
      { cache: "no-store" },
    );
    if (!upstream.ok || !upstream.body) {
      return Response.json(
        { detail: upstream.status === 404 ? "Ek dosya bulunamadi" : "Ek dosya alinamadi" },
        { status: upstream.status === 404 ? 404 : 502 },
      );
    }
    const headers = new Headers();
    for (const name of ["content-type", "content-length", "content-disposition"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("cache-control", "private, no-store");
    headers.set("x-content-type-options", "nosniff");
    return new Response(upstream.body, { status: 200, headers });
  } catch {
    return Response.json({ detail: "API servisine ulasilamadi" }, { status: 502 });
  }
}
