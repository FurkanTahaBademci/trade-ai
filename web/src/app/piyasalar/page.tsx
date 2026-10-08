import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { Instrument, MarketHeatmapData } from "@/lib/types";
import { PiyasalarView } from "@/components/piyasalar-view";
import { PageHeader, ServiceNotice } from "@/components/ui";

export const metadata: Metadata = { title: "Piyasalar & Sektörel Isı Haritası" };

export default async function MarketsPage() {
  const [instruments, heatmap] = await Promise.all([
    apiGet<Instrument[]>("/api/instruments", []),
    apiGet<MarketHeatmapData | null>("/api/markets/heatmap", null),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="BIST evreni & Sektörler"
        title="Piyasalar"
        description="Borsa İstanbul sektör performanslarını ısı haritasında keşfedin; fiyat, hacim ve teknik sinyallere tek bakışta ulaşın."
        actions={
          instruments.ok ? (
            <span className="pill pill-positive">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]" />
              {instruments.data.length.toLocaleString("tr-TR")} şirket
            </span>
          ) : undefined
        }
      />
      <ServiceNotice show={!instruments.ok} />
      <PiyasalarView
        instruments={instruments.data}
        heatmap={heatmap.data}
      />
    </>
  );
}


