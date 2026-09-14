import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { CompositeSignal, SignalHorizonStat, SystemStats } from "@/lib/types";
import { PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";
import { InfiniteSignalFeed } from "@/components/infinite-signal-feed";
import { SignalAccuracyTable } from "@/components/signal-accuracy-table";

export const metadata: Metadata = { title: "Bileşik Sinyaller" };

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ label?: string }> }) {
  const { label } = await searchParams; const query = label ? `&label=${encodeURIComponent(label)}` : "";
  const [result, accuracy, statsRes] = await Promise.all([
    apiGet<CompositeSignal[]>(`/api/signals?limit=15${query}`, []),
    apiGet<SignalHorizonStat[]>("/api/signals/accuracy", []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.signals_total;
  const vpCount = stats?.signals_by_label?.["VERY_POSITIVE"];
  const pCount = stats?.signals_by_label?.["POSITIVE"];
  const nCount = stats?.signals_by_label?.["NEUTRAL"];

  return <><PageHeader eyebrow="Sürüm v1 · Teknik sıralama" title="Bileşik Sinyaller" description="AI etkisi, temel analiz, analist konsensüsü ve fon akımının açıklanabilir 0–100 bileşik görünümü." actions={<div className="flex flex-wrap items-center gap-2">{total ? <span className="pill pill-positive mr-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total} hisse</span> : null}<Filter href="/sinyaller" active={!label}>Tümü{total ? ` (${total})` : ""}</Filter><Filter href="/sinyaller?label=VERY_POSITIVE" active={label === "VERY_POSITIVE"}>Çok pozitif{vpCount != null ? ` (${vpCount})` : ""}</Filter><Filter href="/sinyaller?label=POSITIVE" active={label === "POSITIVE"}>Pozitif{pCount != null ? ` (${pCount})` : ""}</Filter><Filter href="/sinyaller?label=NEUTRAL" active={label === "NEUTRAL"}>Nötr{nCount != null ? ` (${nCount})` : ""}</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <InfiniteSignalFeed key={label ?? "all"} initialItems={result.data} label={label}/>
    <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu skor teknik bir araştırma ve sıralama göstergesidir; yatırım tavsiyesi veya otomatik al-sat emri değildir.</p>
    <section className="mt-8"><SectionTitle title="Sinyal doğruluğu" subtitle="Geçmişte üretilen etiketlerin, kendisinden sonraki gerçek fiyat hareketiyle karşılaştırılması"/>{accuracy.ok ? <SignalAccuracyTable stats={accuracy.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Getiri, sinyal tarihinden sonraki ilk mevcut kapanıştan (bakış-önyargısı olmadan) N işlem günü sonraki kapanışa göre hesaplanır. İsabet oranı yalnız yönlü etiketlerde (pozitif/negatif) anlamlıdır; nötr etiketin yönlü bir beklentisi yoktur. Bu bir backtest değildir — komisyon/kayma/pozisyon boyutu içermez, yalnız yön tahmininin isabetini ölçer.</p></section></>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

