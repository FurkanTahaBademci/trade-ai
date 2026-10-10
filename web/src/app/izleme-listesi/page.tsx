import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { WatchlistView } from "@/components/watchlist-view";

export const metadata: Metadata = { title: "İzleme Listesi" };

export default function WatchlistPage() {
  return <>
    <PageHeader eyebrow="Kişisel izleme listesi" title="İzleme Listesi" description="Takip etmek istediğiniz hisseleri hisse sayfalarındaki veya listelerdeki yıldıza tıklayarak ekleyin."/>
    <WatchlistView/>
  </>;
}
