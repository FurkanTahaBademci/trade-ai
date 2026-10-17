import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { ComponentPower, CompositeSignal, SignalHorizonStat, SignalMovers, SystemStats, WeightScenario } from "@/lib/types";
import { Icon } from "@/components/icon";
import { PageHeader,ServiceNotice, SectionTitle } from "@/components/ui";
import { InfiniteSignalFeed } from "@/components/infinite-signal-feed";
import { SignalAccuracyTable } from "@/components/signal-accuracy-table";
import { SignalMoversPanel, moverPeriod } from "@/components/signal-movers";
import { ComponentPowerTable, WeightScenarioTable } from "@/components/component-power-table";

export const metadata: Metadata = { title: "Bileşik Sinyaller" };

const LABELS = new Set(["VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"]);

type View = "siralama" | "dogruluk";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ label?: string; degisim?: string; gorunum?: string }> }) {
  const params = await searchParams; const label = params.label && LABELS.has(params.label) ? params.label : undefined; const query = label ? `&label=${encodeURIComponent(label)}` : "";
  const view: View = params.gorunum === "dogruluk" ? "dogruluk" : "siralama";
  const period = moverPeriod(params.degisim);
  // Sonsuz liste analiz bölümlerini aşağı ittiği için ikisi ayrı sekmede; yalnız açık sekmenin verisi çekilir.
  const empty = { data: [], ok: true as const };
  const [result, accuracy, statsRes, movers, power, scenarios] = await Promise.all([
    // Bileşik skorlar toplu yeniden hesaplanıyor (en sık ~10 dk); 60 sn önbellek yeterli.
    apiGet<CompositeSignal[]>(`/api/signals?limit=15${query}`, [], { revalidate: 60 }),
    view === "dogruluk" ? apiGet<SignalHorizonStat[]>("/api/signals/accuracy", [], { revalidate: 900 }) : Promise.resolve(empty),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
    view === "siralama" ? apiGet<SignalMovers | null>(`/api/signals/movers?days=${period.days}&limit=6`, null, { revalidate: 300 }) : Promise.resolve({ data: null, ok: true as const }),
    view === "dogruluk" ? apiGet<ComponentPower[]>("/api/signals/component-power", [], { revalidate: 900 }) : Promise.resolve(empty),
    view === "dogruluk" ? apiGet<WeightScenario[]>("/api/signals/weight-scenarios", [], { revalidate: 900 }) : Promise.resolve(empty),
  ]);
  const moversHref = (days: number) => { const next = new URLSearchParams(); if (label) next.set("label", label); if (days !== 7) next.set("degisim", String(days)); const text = next.toString(); return text ? `/sinyaller?${text}` : "/sinyaller"; };
  const labelHref = (value?: string) => { const next = new URLSearchParams(); if (value) next.set("label", value); if (period.days !== 7) next.set("degisim", String(period.days)); const text = next.toString(); return text ? `/sinyaller?${text}` : "/sinyaller"; };
  const stats = statsRes.data;
  const total = stats?.signals_total;
  const counts = stats?.signals_by_label ?? {};
  const modelVersion = result.data[0]?.model_version;

  return <><PageHeader eyebrow="Günlük hisse sıralaması" title="Bileşik Sinyaller" description="Her hisse için AI haber etkisi, temel analiz, analist konsensüsü ve BIST100'e göre fiyat momentumu birleştirilerek 0–100 arası tek bir skor üretilir. Az veriye dayanan skorlar 50'ye (nötr) doğru çekilir." actions={<nav className="flex rounded border border-[var(--border)] bg-[var(--surface-raised)] p-1" aria-label="Sinyal görünümü">
    <Tab href={labelHref(label)} active={view === "siralama"}>Sıralama</Tab>
    <Tab href="/sinyaller?gorunum=dogruluk" active={view === "dogruluk"}>Doğruluk &amp; model</Tab>
  </nav>}/><ServiceNotice show={!result.ok}/>
    {view === "siralama" ? <>
      <div className="-mx-3 mb-4 flex gap-2 overflow-x-auto whitespace-nowrap px-3 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0" aria-label="Sinyal etiketi filtresi">
        <Filter href={labelHref()} active={!label}>Tümü{total ? ` (${total})` : ""}</Filter>
        {LABEL_FILTERS.map(([value, text]) => <Filter key={value} href={labelHref(value)} active={label === value}>{text}{counts[value] != null ? ` (${counts[value]})` : ""}</Filter>)}
        <a href={`/api/export/signals${label ? `?label=${encodeURIComponent(label)}` : ""}`} download className="pill shrink-0 transition hover:text-[var(--text)]"><Icon name="download" size={12}/>CSV indir</a>
      </div>
      <SignalMoversPanel movers={movers.data} days={period.days} hrefFor={moversHref}/>
      <p className="mb-3 text-[11px] leading-5 text-[var(--text-muted)]">Skorların geçmişte ne kadar isabetli olduğunu ve hangi bileşenin işe yaradığını <Link href="/sinyaller?gorunum=dogruluk" className="font-medium text-[var(--primary)] hover:underline">Doğruluk &amp; model</Link> sekmesinde görebilirsiniz.</p>
      <InfiniteSignalFeed key={label ?? "all"} initialItems={result.data} label={label}/>
      <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu skor teknik bir araştırma ve sıralama göstergesidir; yatırım tavsiyesi veya otomatik al-sat emri değildir.</p>
    </> : <>
      {modelVersion && <p className="mb-6 text-[11px] leading-5 text-[var(--text-muted)]">Canlı skor formülü: <span className="terminal-mono text-[var(--text-secondary)]">{modelVersion}</span> — bileşenler veya ağırlıklar değiştiğinde sürüm numarası artar; aşağıdaki ölçümler hangi değişikliğin işe yarayacağına karar vermek için toplanır.</p>}
      <section><SectionTitle title="Sinyal doğruluğu" subtitle="Geçmişte üretilen etiketlerin, kendisinden sonraki gerçek fiyat hareketiyle karşılaştırılması"/>{accuracy.ok ? <SignalAccuracyTable stats={accuracy.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Getiri, sinyal tarihinden sonraki ilk mevcut kapanıştan (bakış-önyargısı olmadan) N işlem günü sonraki kapanışa göre hesaplanır. Ana değer aynı dönemdeki BIST100 getirisinin çıkarıldığı fazla getiridir; düşen piyasada mutlak getiri tüm etiketlerde negatif çıkacağı için asıl ölçü budur. Endeksi yenme oranı yalnız yönlü etiketlerde (pozitif/negatif) anlamlıdır. Bu bir backtest değildir — komisyon/kayma/pozisyon boyutu içermez, yalnız yön tahmininin isabetini ölçer.</p></section>
      <section className="mt-8"><SectionTitle title="Bileşenlerin tahmin gücü" subtitle="Hangi bileşen, yüksek puan verdiği hisselerin sonradan daha çok kazanacağını doğru sıralıyor?"/>{power.ok ? <ComponentPowerTable rows={power.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Her işlem günü hisseler bileşen skoruna göre sıralanır ve sonraki N işlem günündeki getirileriyle sıra korelasyonu (IC, bilgi katsayısı) hesaplanır; tabloda günlük IC ortalaması, IC'nin pozitif olduğu günlerin oranı ve en yüksek beşte birlik dilimle en düşük dilim arasındaki ortalama getiri farkı yer alır. Aynı gün tüm hisseler aynı piyasayı yaşadığı için endeks düzeltmesi gerekmez. 0'ın üstü yüksek skorun daha yüksek getiriyle birlikte geldiğini gösterir; ±0,02 içi gürültü sayılır. Vadeler örtüştüğü için günler birbirinden bağımsız değildir; kısa geçmişte sonuçlar dalgalıdır.</p></section>
      <section className="mt-8"><SectionTitle title="Ağırlık senaryoları" subtitle="Bileşenler farklı ağırlıklarla birleştirilseydi skor hisseleri ne kadar iyi sıralardı?"/>{scenarios.ok ? <WeightScenarioTable rows={scenarios.data}/> : <ServiceNotice show/>}<p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">Her senaryoda skor, saklanan bileşen skorlarından o ağırlıklarla yeniden hesaplanır ve yukarıdaki tabloyla aynı yöntemle (günlük sıra korelasyonu) ölçülür. Canlı model değişmez; bu tablo bir sonraki model sürümü için kanıt toplar. Aynı geçmişte en iyi görünen ağırlık geleceğe aynen taşınmayabilir: birkaç haftalık farklar gürültü olabilir, karar için en az birkaç aylık tutarlılık aranmalıdır.</p></section>
    </>}</>;
}

const LABEL_FILTERS: [string, string][] = [["VERY_POSITIVE", "Çok pozitif"], ["POSITIVE", "Pozitif"], ["NEUTRAL", "Nötr"], ["NEGATIVE", "Negatif"], ["VERY_NEGATIVE", "Çok negatif"]];

function Tab({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link prefetch={false} href={href} aria-current={active ? "page" : undefined} className={`rounded px-3 py-1.5 text-xs font-semibold transition ${active ? "bg-[var(--primary)] text-[var(--primary-contrast)]" : "text-[var(--text-muted)] hover:text-[var(--text)]"}`}>{children}</Link>; }

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link prefetch={false} href={href} aria-current={active ? "true" : undefined} className={`pill shrink-0 transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

