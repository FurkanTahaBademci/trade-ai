import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { CompositeSignal } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteSignalFeed } from "@/components/infinite-signal-feed";

export const metadata: Metadata = { title: "Bileşik Sinyaller" };

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ label?: string }> }) {
  const { label } = await searchParams; const query = label ? `&label=${encodeURIComponent(label)}` : "";
  const result = await apiGet<CompositeSignal[]>(`/api/signals?limit=15${query}`, []);
  return <><PageHeader eyebrow="Sürüm v1 · Teknik sıralama" title="Bileşik Sinyaller" description="AI etkisi, temel analiz, analist konsensüsü ve fon akımının açıklanabilir 0–100 bileşik görünümü." actions={<div className="flex flex-wrap gap-2"><Filter href="/sinyaller" active={!label}>Tümü</Filter><Filter href="/sinyaller?label=VERY_POSITIVE" active={label === "VERY_POSITIVE"}>Çok pozitif</Filter><Filter href="/sinyaller?label=POSITIVE" active={label === "POSITIVE"}>Pozitif</Filter><Filter href="/sinyaller?label=NEUTRAL" active={label === "NEUTRAL"}>Nötr</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <InfiniteSignalFeed key={label ?? "all"} initialItems={result.data} label={label}/>
    <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu skor teknik bir araştırma ve sıralama göstergesidir; yatırım tavsiyesi veya otomatik al-sat emri değildir.</p></>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
