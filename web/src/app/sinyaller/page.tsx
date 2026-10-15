import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { ComponentPower, CompositeSignal, SignalHorizonStat, SignalMovers, SystemStats } from "@/lib/types";
import { Icon } from "@/components/icon";
import { PageHeader,ServiceNotice, SectionTitle } from "@/components/ui";
import { InfiniteSignalFeed } from "@/components/infinite-signal-feed";
import { SignalAccuracyTable } from "@/components/signal-accuracy-table";
import { SignalMoversPanel, moverPeriod } from "@/components/signal-movers";
import { ComponentPowerTable } from "@/components/component-power-table";

export const metadata: Metadata = { title: "Bileşik Sinyaller" };

const LABELS = new Set(["VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"]);

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ label?: string; degisim?: string }> }) {
  const params = await searchParams; const label = params.label && LABELS.has(params.label) ? params.label : undefined; const query = label ? `&label=${encodeURIComponent(label)}` : "";
  const period = moverPeriod(params.degisim);
  const [result, accuracy, statsRes, movers, power] = await Promise.all([
    apiGet<CompositeSignal[]>(`/api/signals?limit=15${query}`, []),
    apiGet<SignalHorizonStat[]>("/api/signals/accuracy", [], { revalidate: 900 }),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
    apiGet<SignalMovers | null>(`/api/signals/movers?days=${period.days}&limit=6`, null, { revalidate: 300 }),
    apiGet<ComponentPower[]>("/api/signals/component-power", [], { revalidate: 900 }),
  ]);
  const moversHref = (days: number) => { const next = new URLSearchParams(); if (label) next.set("label", label); if (days !== 7) next.set("degisim", String(days)); const text = next.toString(); return text ? `/sinyaller?${text}` : "/sinyaller"; };
  const stats = statsRes.data;
  const total = stats?.signals_total;
  const vpCount = stats?.signals_by_label?.["VERY_POSITIVE"];
  const pCount = stats?.signals_by_label?.["POSITIVE"];
  const nCount = stats?.signals_by_label?.["NEUTRAL"];
  const negCount = stats?.signals_by_label?.["NEGATIVE"];
  const vnCount = stats?.signals_by_label?.["VERY_NEGATIVE"];

  return <><PageHeader eyebrow="Sürüm v3 · Teknik sıralama" title="Bileşik Sinyaller" description="AI etkisi, temel analiz, analist konsensüsü ve BIST100'e göre fiyat momentumunun açıklanabilir 0–100 bileşik görünümü. Az kanıta dayanan skorlar nötre doğru çekilir." actions={<div className="flex flex-wrap items-center gap-2">{total ? <span className="pill pill-positive mr-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total} hisse</span> : null}<Filter href="/sinyaller" active={!label}>Tümü{total ? ` (${total})` : ""}</Filter><Filter href="/sinyaller?label=VERY_POSITIVE" active={label === "VERY_POSITIVE"}>Çok pozitif{vpCount != null ? ` (${vpCount})` : ""}</Filter><Filter href="/sinyaller?label=POSITIVE" active={label === "POSITIVE"}>Pozitif{pCount != null ? ` (${pCount})` : ""}</Filter><Filter href="/sinyaller?label=NEUTRAL" active={label === "NEUTRAL"}>Nötr{nCount != null ? ` (${nCount})` : ""}</Filter><Filter href="/sinyaller?label=NEGATIVE" active={label === "NEGATIVE"}>Negatif{negCount != null ? ` (${negCount})` : ""}</Filter><Filter href="/sinyaller?label=VERY_NEGATIVE" active={label === "VERY_NEGATIVE"}>Çok negatif{vnCount != null ? ` (${vnCount})` : ""}</Filter><a href={`/api/export/signals${label ? `?label=${encodeURIComponent(label)}` : ""}`} download className="pill transition hover:text-[var(--text)]"><Icon name="download" size={12}/>CSV indir</a></div>}/><ServiceNotice show={!result.ok}/>
    <SignalMoversPanel movers={movers.data} days={period.days} hrefFor={moversHref}/>
    <InfiniteSignalFeed key={label ?? "all"} initialItems={result.data} label={label}/>
    <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu skor teknik bir araştırma ve sıralama göstergesidir; yatırım tavsiyesi veya otomatik al-sat emri değildir.</p>
    <section className="mt-8"><SectionTitle title="Sinyal doğruluğu" subtitle="Geçmişte üretilen etiketlerin, kendisinden sonraki gerçek fiyat hareketiyle karşılaştırılması"/>{accuracy.ok ? <SignalAccuracyTable stats={accuracy.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Getiri, sinyal tarihinden sonraki ilk mevcut kapanıştan (bakış-önyargısı olmadan) N işlem günü sonraki kapanışa göre hesaplanır. Ana değer aynı dönemdeki BIST100 getirisinin çıkarıldığı fazla getiridir; düşen piyasada mutlak getiri tüm etiketlerde negatif çıkacağı için asıl ölçü budur. Endeksi yenme oranı yalnız yönlü etiketlerde (pozitif/negatif) anlamlıdır. Bu bir backtest değildir — komisyon/kayma/pozisyon boyutu içermez, yalnız yön tahmininin isabetini ölçer.</p></section>
    <section className="mt-8"><SectionTitle title="Bileşenlerin tahmin gücü" subtitle="Hangi bileşen, yüksek puan verdiği hisselerin sonradan daha çok kazanacağını doğru sıralıyor?"/>{power.ok ? <ComponentPowerTable rows={power.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Her işlem günü hisseler bileşen skoruna göre sıralanır ve sonraki N işlem günündeki getirileriyle sıra korelasyonu (IC) hesaplanır; tabloda günlük IC ortalaması, IC'nin pozitif olduğu günlerin oranı ve en yüksek beşte birlik dilimle en düşük dilim arasındaki ortalama getiri farkı yer alır. Aynı gün tüm hisseler aynı piyasayı yaşadığı için endeks düzeltmesi gerekmez. 0'ın üstü yüksek skorun daha yüksek getiriyle birlikte geldiğini gösterir; ±0,02 içi gürültü sayılır. Vadeler örtüştüğü için günler birbirinden bağımsız değildir; kısa geçmişte sonuçlar dalgalıdır.</p></section></>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

