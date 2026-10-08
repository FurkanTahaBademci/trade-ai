import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { NewsArticle, SystemStats } from "@/lib/types";
import { sourceName } from "@/lib/format";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteNewsFeed } from "@/components/infinite-news-feed";

export const metadata: Metadata = { title: "Haber Akışı" };

const NEWS_SOURCES = ["bloomberght", "investing_tr", "aa_ekonomi", "dunya", "foreks", "trthaber"];

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ source?: string; mode?: string }>;
}) {
  const { source, mode: requestedMode } = await searchParams;
  const mode: "smart" | "chronological" = requestedMode === "chronological" ? "chronological" : "smart";

  const queryParts = [`mode=${mode}`];
  if (source) queryParts.push(`source=${encodeURIComponent(source)}`);
  const query = `&${queryParts.join("&")}`;

  const [news, statsRes] = await Promise.all([
    apiGet<NewsArticle[]>(`/api/news?limit=12${query}`, []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.news_total;

  const buildUrl = (targetMode: "smart" | "chronological", targetSource?: string) => {
    const params = new URLSearchParams();
    if (targetMode !== "smart") params.set("mode", targetMode);
    if (targetSource) params.set("source", targetSource);
    const qs = params.toString();
    return `/haberler${qs ? `?${qs}` : ""}`;
  };

  return (
    <>
      <PageHeader
        eyebrow="Piyasa istihbaratı"
        title="Haber Akışı"
        description="Güvenilir finans kaynaklarından toplanan, AI önem derecesi ve güncellik analizleriyle zenginleştirilmiş BIST haberleri."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {total ? (
              <span className="pill pill-positive mr-1">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]" />
                {total.toLocaleString("tr-TR")} haber
              </span>
            ) : null}
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

      {/* Mode Switcher: Smart vs Chronological */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
        <div className="flex rounded border border-[var(--border)] p-1 bg-[var(--surface-raised)]">
          <Link
            href={buildUrl("smart", source)}
            className={`flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-semibold transition ${
              mode === "smart"
                ? "bg-[var(--primary)] text-[var(--primary-contrast)]"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            Öne çıkanlar
          </Link>
          <Link
            href={buildUrl("chronological", source)}
            className={`flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-semibold transition ${
              mode === "chronological"
                ? "bg-[var(--primary)] text-[var(--primary-contrast)]"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            Kronolojik akış
          </Link>
        </div>

        <p className="text-xs text-[var(--text-muted)]">
          {mode === "smart" ? (
            <span>
              AI etki puanı ve güncellik harmanlanarak sıralandı · Önemsiz (0 puanlı) haberler gizlendi
            </span>
          ) : (
            <span>Tüm haberler en yeniden eskiye doğru ham yayın sırasında gösteriliyor</span>
          )}
        </p>
      </div>

      <ServiceNotice show={!news.ok} />
      <InfiniteNewsFeed
        key={`${source ?? "all"}-${mode}`}
        initialItems={news.data}
        source={source}
        mode={mode}
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
    <Link
      href={href}
      className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}
    >
      {children}
    </Link>
  );
}
