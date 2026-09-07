import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { Instrument } from "@/lib/types";
import { InstrumentList } from "@/components/instrument-list";
import { PageHeader, ServiceNotice } from "@/components/ui";

export const metadata: Metadata = { title: "Piyasalar" };

export default async function MarketsPage() {
  const instruments = await apiGet<Instrument[]>("/api/instruments", []);
  return <><PageHeader eyebrow="BIST evreni" title="Piyasalar" description="Aktif Borsa İstanbul şirketlerini keşfedin; fiyat, temel analiz ve kurumsal görüş detaylarına ulaşın."/><ServiceNotice show={!instruments.ok}/><InstrumentList instruments={instruments.data}/></>;
}
