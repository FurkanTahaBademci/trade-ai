import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { Disclosure, SystemStats } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteKapFeed } from "@/components/infinite-kap-feed";

export const metadata: Metadata = { title: "KAP Bildirimleri" };

export default async function KapPage() {
  const [result, statsRes] = await Promise.all([
    apiGet<Disclosure[]>("/api/disclosures?limit=15", []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const total = statsRes.data?.disclosures_total;
  return <><PageHeader eyebrow="Resmî açıklamalar" title="KAP Bildirimleri" description="Borsa İstanbul şirketlerinin güncel bildirimleri, sınıflandırmaları ve indirilebilir ekleri." actions={total ? <span className="pill pill-positive"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total.toLocaleString("tr-TR")} bildirim</span> : undefined}/><ServiceNotice show={!result.ok}/><InfiniteKapFeed initialItems={result.data}/></>;
}

