import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { CompanyComparisonData } from "@/lib/types";
import { CompanyCompareView } from "@/components/company-compare";
import { PageHeader, ServiceNotice } from "@/components/ui";

export const metadata: Metadata = {
  title: "Şirket Karşılaştırma",
  description: "BIST şirketlerini değerleme çarpanları, kârlılık rasyoları, analist beklentileri ve AI duygu puanlarıyla yan yana karşılaştırın.",
};

import { normalizeTicker } from "@/lib/turkish";

type PageProps = {
  searchParams: Promise<{ tickers?: string }>;
};

export default async function ComparePage({ searchParams }: PageProps) {
  const params = await searchParams;
  const rawParam = params?.tickers || "THYAO,PGSUS";
  const normalizedTickers = rawParam
    .split(",")
    .map((t) => normalizeTicker(t))
    .filter(Boolean)
    .join(",");
  const safeTickers = normalizedTickers || "THYAO,PGSUS";

  const comparison = await apiGet<CompanyComparisonData | null>(
    `/api/markets/compare?tickers=${encodeURIComponent(safeTickers)}`,
    null
  );


  return (
    <>
      <PageHeader
        eyebrow="Şirket Analizi & Kıyaslama"
        title="Şirket Karşılaştırma"
        description="Aynı sektör veya farklı pazarlardaki BIST şirketlerini F/K, PD/DD, ROE, konsensüs hedef fiyatları ve AI kompozit sinyalleriyle 5 eksende kıyaslayın."
        actions={
          comparison.ok && comparison.data ? (
            <span className="pill pill-positive">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]" />
              {comparison.data.companies.length} Şirket Kıyaslanıyor
            </span>
          ) : undefined
        }
      />
      <ServiceNotice show={!comparison.ok} />
      <CompanyCompareView initialData={comparison.data} />
    </>
  );
}
