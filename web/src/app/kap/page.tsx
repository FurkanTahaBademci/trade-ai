import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { Disclosure } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteKapFeed } from "@/components/infinite-kap-feed";

export const metadata: Metadata = { title: "KAP Bildirimleri" };

export default async function KapPage() {
  const result = await apiGet<Disclosure[]>("/api/disclosures?limit=15", []);
  return <><PageHeader eyebrow="Resmî açıklamalar" title="KAP Bildirimleri" description="Borsa İstanbul şirketlerinin güncel bildirimleri, sınıflandırmaları ve indirilebilir ekleri."/><ServiceNotice show={!result.ok}/><InfiniteKapFeed initialItems={result.data}/></>;
}
