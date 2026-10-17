import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { NewsArticle, SystemStats } from "@/lib/types";
import { sourceName } from "@/lib/format";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteNewsFeed } from "@/components/infinite-news-feed";
import { TickerFilter, tickerParam } from "@/components/ticker-filter";

export const metadata: Metadata = { title: "Haber Akışı" };

const NEWS_SOURCES = ["bloomberght", "investing_tr", "aa_ekonomi", "dunya", "foreks", "trthaber"];

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ source?: string; mode?: string; hisse?: string }>;
}) {
  const { source: requestedSource, mode: requestedMode, hisse } = await searchParams;
  const source = requestedSource && NEWS_SOURCES.includes(requestedSource) ? requestedSource : undefined;
  const ticker = tickerParam(hisse);
  const mode: "smart" | "chronological" = requestedMode === "chronological" ? "chronological" : "smart";

  // Akıllı sıralama zamana bağlı; sonsuz kaydırmadaki tüm sayfalar ilk sayfanın
  // zamanıyla sıralanır ki haberler tekrar etmesin veya atlanmasın.
  const ref = mode === "smart" ? new Date().toISOString() : undefined;
  const queryParts = [`mode=${mode}`];
  if (ref) queryParts.push(`ref=${encodeURIComponent(ref)}`);
  if (source) queryParts.push(`source=${encodeURIComponent(source)}`);
  if (ticker) queryParts.push(`ticker=${ticker}`);
  const query = `&${queryParts.join("&")}`;

  const [news, statsRes] = await Promise.all([
    // İlk sayfa 30 sn önbellekli; sonraki sayfalar canlı akıştan gelir ve tekrarlar ayıklanır.
    apiGet<NewsArticle[]>(`/api/news?limit=12${query}`, [], { revalidate: 30 }),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.news_total;

  const buildUrl = (targetMode: "smart" | "chronological", targetSource?: string) => {
    const params = new URLSearchParams();
    if (targetMode !== "smart") params.set("mode", targetMode);
    if (targetSource) params.set("source", targetSource);
    if (ticker) params.set("hisse", ticker);
    const qs = params.toString();
    return `/haberler${qs ? `?${qs}` : ""}`;
  };

  return (
    <>
      <PageHeader
        eyebrow="Piyasa istihbaratı"
        title="Haber Akışı"
        description="Finans kaynaklarından toplanan, yapay zekâ önem puanı ve güncelliğe göre sıralanan BIST haberleri."
        actions={
          // Mobilde kaynak çipleri tek satırda yatay kaydırılır; ilk haber ekrana sığsın.
          <div className="-mx-3 flex w-[calc(100%+1.5rem)] gap-2 overflow-x-auto whitespace-nowrap px-3 pb-1 [scrollbar-width:none] sm:mx-0 sm:w-auto sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0" aria-label="Kaynak filtresi">
            <Filter href={buildUrl(mode)} active={!source}>
              Tümü{total ? ` (${total.toLocaleString("tr-TR")})` : ""}
            </Filter>
            {NEWS_SOURCES.map((name) => {
              const count = stats?.news_by_source?.[name];
              return (
                <Filter key={name} href={buildUrl(mode, name)} active={source === name}>
                  {sourceName(name)}
                  {count != null ? ` (${count.toLocaleString("tr-TR")})` : ""}
                </Filter>
              );
            })}
          </div>
        }
      />

      {/* Sıralama modu ve hisse filtresi tek satırda; mobilde gerekirse alta kayar. */}
      <div className="mb-1 flex flex-wrap items-start gap-x-3 gap-y-2">
        <div className="flex shrink-0 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-1" role="group" aria-label="Sıralama">
          <Link prefetch={false}
            href={buildUrl("smart", source)}
            aria-current={mode === "smart" ? "true" : undefined}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition ${
              mode === "smart"
                ? "bg-[var(--primary)] text-[var(--primary-contrast)]"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            title="AI etki puanı ve güncellik harmanlanarak sıralanır; önemsiz (0 puanlı) haberler gizlenir"
          >
            Öne çıkanlar
          </Link>
          <Link prefetch={false}
            href={buildUrl("chronological", source)}
            aria-current={mode === "chronological" ? "true" : undefined}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition ${
              mode === "chronological"
                ? "bg-[var(--primary)] text-[var(--primary-contrast)]"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            title="Tüm haberler en yeniden eskiye doğru"
          >
            Kronolojik
          </Link>
        </div>
        <TickerFilter action="/haberler" ticker={ticker} keep={{ source, mode: mode === "smart" ? undefined : mode }} />
      </div>
      <p className="mb-3 hidden text-xs text-[var(--text-muted)] sm:block">
        {mode === "smart"
          ? "AI etki puanı ve güncellik harmanlanarak sıralandı · Önemsiz (0 puanlı) haberler gizlendi"
          : "Tüm haberler en yeniden eskiye doğru ham yayın sırasında gösteriliyor"}
      </p>
      <ServiceNotice show={!news.ok} />
      <InfiniteNewsFeed
        key={`${source ?? "all"}-${mode}-${ticker ?? "all"}`}
        initialItems={news.data}
        source={source}
        mode={mode}
        ticker={ticker}
        rankingRef={ref}
      />
    </>
  );
}

function Filter({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link prefetch={false}
      href={href}
      aria-current={active ? "true" : undefined}
      className={`pill shrink-0 transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}
    >
      {children}
    </Link>
  );
}
