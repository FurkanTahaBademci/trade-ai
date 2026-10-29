import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { OrderForm } from "@/components/order-form";
import { PageHeader } from "@/components/ui";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import type { MyPortfolioSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Paper emri", robots: { index: false, follow: false } };

/** Hisse sayfasındaki "Paper emri ver" bağlantısının hedefi: manuel portföy seçip emir verir. */
export default async function PaperOrderPage({ searchParams }: { searchParams: Promise<{ hisse?: string }> }) {
  const [params, account, token] = await Promise.all([searchParams, currentAccount(), sessionToken()]);
  const ticker = (params.hisse ?? "").toLocaleUpperCase("tr-TR").replace(/[^A-Z0-9]/g, "").slice(0, 16);
  const here = `/portfoylerim/emir${ticker ? `?hisse=${ticker}` : ""}`;
  if (!account || !token) redirect(`/giris?next=${encodeURIComponent(here)}`);
  const portfolios = await accountRequest<MyPortfolioSummary[]>("/api/me/portfolios", token);
  const manual = (portfolios.ok ? portfolios.data : []).filter((item) => item.kind === "MANUAL" && item.status === "ACTIVE");

  return <div className="max-w-xl">
    <PageHeader eyebrow="Portföylerim · Simülasyon" title={ticker ? `${ticker} için paper emri` : "Paper emri"} description="Manuel portföyüne sanal alış ya da satış emri ver. Gerçek emir iletilmez."/>
    {!portfolios.ok && <p role="alert" className="mb-4 text-sm text-[var(--negative)]">{portfolios.message}</p>}
    {portfolios.ok && !manual.length
      ? <div className="panel-flat p-5 text-sm leading-6 text-[var(--text-secondary)]"><p>Emir vermek için etkin bir manuel portföyün olmalı. Strateji portföyleri emir almaz; alım-satımı sinyal kuralları yapar.</p><Link prefetch={false} href="/portfoylerim/yeni?tur=MANUAL" className="mt-4 inline-flex h-9 items-center rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Manuel portföy oluştur</Link></div>
      : <div className="panel-flat p-5"><OrderForm portfolios={manual.map((item) => ({ id: item.id, name: item.name, cash: item.cash_balance }))} ticker={ticker}/></div>}
  </div>;
}
