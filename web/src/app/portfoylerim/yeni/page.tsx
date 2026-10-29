import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { NewPortfolioForm } from "@/components/new-portfolio-form";
import { PageHeader } from "@/components/ui";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import type { StrategyTemplate } from "@/lib/types";

export const metadata: Metadata = { title: "Yeni portföy", robots: { index: false, follow: false } };

export default async function NewPortfolioPage({ searchParams }: { searchParams: Promise<{ tur?: string }> }) {
  const [account, token, params] = await Promise.all([currentAccount(), sessionToken(), searchParams]);
  if (!account || !token) redirect("/giris?next=/portfoylerim/yeni");
  const templates = await accountRequest<StrategyTemplate[]>("/api/me/portfolios/templates", token);
  return <div className="max-w-4xl">
    <PageHeader eyebrow="Portföylerim" title="Yeni paper portföy" description="Sanal bakiyeyle çalışır; gerçek emir iletilmez ve yatırım tavsiyesi değildir."/>
    {templates.ok
      ? <NewPortfolioForm templates={templates.data} initialKind={params.tur === "MANUAL" ? "MANUAL" : "STRATEGY"}/>
      : <p role="alert" className="text-sm text-[var(--negative)]">{templates.message}</p>}
  </div>;
}
