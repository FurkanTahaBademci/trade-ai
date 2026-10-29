import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { IndexPrice, PaperPortfolio, PaperPosition, PaperRisk, PaperSnapshot, PaperTrade } from "@/lib/types";
import { EmptyState, PageHeader, ServiceNotice } from "@/components/ui";
import { PaperPortfolioView } from "@/components/paper-portfolio-view";

export const metadata: Metadata = { title: "Model Portföy" };

export default async function PortfolioPage() {
  // Herkese açık model portföy; işlemleri worker yazıyor (fiyat/sinyal turlarında).
  // 30 sn önbellek hisse sayfasındaki portföy kutusuyla aynı tazelikte.
  const portfolios = await apiGet<PaperPortfolio[]>("/api/paper/portfolios", [], { revalidate: 30 }); const portfolio = portfolios.data[0];
  const [positions, trades, performance, risk] = portfolio ? await Promise.all([
    apiGet<PaperPosition[]>(`/api/paper/portfolios/${portfolio.id}/positions`, [], { revalidate: 30 }), apiGet<PaperTrade[]>(`/api/paper/portfolios/${portfolio.id}/trades?limit=100`, [], { revalidate: 30 }), apiGet<PaperSnapshot[]>(`/api/paper/portfolios/${portfolio.id}/performance?limit=365`, [], { revalidate: 30 }), apiGet<PaperRisk | null>(`/api/paper/portfolios/${portfolio.id}/risk`, null, { revalidate: 30 }),
  ]) : [{ data: [], ok: true as const }, { data: [], ok: true as const }, { data: [], ok: true as const }, { data: null as PaperRisk | null, ok: true as const }];
  const earliestSnapshot = performance.data.map((row) => row.snapshot_date).sort()[0];
  const indexPrices = earliestSnapshot ? await apiGet<IndexPrice[]>(`/api/index/XU100/prices?start=${earliestSnapshot}`, [], { revalidate: 300 }) : { data: [] as IndexPrice[], ok: true as const };
  const serviceDown = !portfolios.ok || !positions.ok || !trades.ok || !performance.ok || !risk.ok;
  return <><PageHeader eyebrow="Simülasyon · Canlı emir yok" title="Model Portföy" description="Bileşik sinyal stratejisinin gerçek EOD fiyatlarıyla, risksiz ve sanal bakiye üzerinde izlenen performansı. Herkes aynı portföyü görür." actions={<div className="flex flex-wrap items-center gap-2">{portfolio && <span className={`pill ${portfolio.status === "ACTIVE" ? "pill-positive" : ""}`}><span className="h-1.5 w-1.5 rounded-full bg-current"/>{portfolio.status === "ACTIVE" ? "Aktif" : "Duraklatıldı"}</span>}<Link prefetch={false} href="/portfoylerim/yeni" className="flex h-8 items-center rounded bg-[var(--primary)] px-3 text-[11px] font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Kendi portföyünü oluştur</Link></div>}/><ServiceNotice show={serviceDown}/>
    {!portfolio ? <div className="panel-flat"><EmptyState title="Paper portföy henüz oluşturulmadı" description="Paper motoru ilk çalıştığında 1.000.000 TL sanal bakiyeyle portföy otomatik oluşturulacak."/></div> : <>
      <PaperPortfolioView portfolio={portfolio} positions={positions.data} trades={trades.data} performance={performance.data} risk={risk.data} indexPrices={indexPrices.data} csvHref={`/api/export/paper-trades?portfolio_id=${portfolio.id}`} positionLimit={10} riskNote="risk kuralları ayarlardan yönetilir"/>
      <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu portföy tamamen sanaldır. Gerçek emir göndermez; komisyon ve fiyat kayması varsayımları içerir.</p></>}
  </>;
}
