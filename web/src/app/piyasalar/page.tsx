import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { Instrument, MarketHeatmapData } from "@/lib/types";
import { PiyasalarView } from "@/components/piyasalar-view";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { parseMarketsView } from "@/lib/markets-view";

export const metadata: Metadata = { title: "Piyasalar & Sektörel Isı Haritası" };

export default async function MarketsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  // Hisse listesi ve ısı haritası herkese açık, fiyat toplayıcısı en sık ~10 dk'da
  // bir yazıyor: kısa önbellek yeterince taze.
  const [instruments, heatmap, initialView] = await Promise.all([
    apiGet<Instrument[]>("/api/instruments", [], { revalidate: 300 }),
    apiGet<MarketHeatmapData | null>("/api/markets/heatmap", null, { revalidate: 60 }),
    searchParams.then(parseMarketsView),
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
        // İstemci yalnız kod ve adı kullanır; diğer alanlar sayfa yükünü büyütmesin.
        instruments={instruments.data.map(({ ticker, name }) => ({ ticker, name }))}
        heatmap={heatmap.data}
        initialView={initialView}
      />
    </>
  );
}


