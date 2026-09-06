/**
 * Faz 0 giris sayfasi: backend /health/detailed endpoint'ini cagirip
 * DB/Redis durumunu gosterir. Faz 9'da bu sayfa gercek dashboard'a
 * (skor siralamasi, gunun en cok degisenleri) donusecek.
 */
async function getHealth() {
  // Server Component container icinden Compose servis adini kullanir;
  // NEXT_PUBLIC_API_URL ileride tarayici tarafindaki istekler icindir.
  const apiUrl =
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/health/detailed`, { cache: "no-store" });
    if (!res.ok) {
      return { status: "error", detail: `HTTP ${res.status}` };
    }
    return await res.json();
  } catch (err) {
    return { status: "error", detail: String(err) };
  }
}

export default async function Home() {
  const health = await getHealth();

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-6 p-8 text-center">
      <h1 className="text-3xl font-bold">trade-ai</h1>
      <p className="text-neutral-400">
        BIST piyasa istihbarati ve paper trading platformu — Faz 0 iskeleti
      </p>

      <div className="w-full rounded-lg border border-neutral-800 bg-neutral-900 p-6 text-left">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Backend Durumu
        </h2>
        <pre className="overflow-x-auto text-sm">
          {JSON.stringify(health, null, 2)}
        </pre>
      </div>

      <p className="text-xs text-neutral-600">
        Faz ilerlemesi: <code>.claude/PROGRESS.md</code>
      </p>
    </main>
  );
}
