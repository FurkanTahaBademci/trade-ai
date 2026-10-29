import type { Metadata } from "next";
import Link from "next/link";
import { EmptyState, PageHeader } from "@/components/ui";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import { formatDate, formatMoney, formatPercent } from "@/lib/format";
import type { MyPortfolioSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Portföylerim" };

const primaryLink = "flex h-9 items-center rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]";

export default async function MyPortfoliosPage({ searchParams }: { searchParams: Promise<{ result?: string; message?: string }> }) {
  const [account, token, notice] = await Promise.all([currentAccount(), sessionToken(), searchParams]);
  if (!account || !token) return <SignedOut/>;
  const portfolios = await accountRequest<MyPortfolioSummary[]>("/api/me/portfolios", token);
  const items = portfolios.ok ? portfolios.data : [];

  return <>
    <PageHeader eyebrow="Simülasyon · Canlı emir yok" title="Portföylerim" description="Kendi kurallarınla çalışan strateji portföyleri ve emirlerini kendin verdiğin manuel portföyler. Tümü sanal bakiyeyle, gerçek gün sonu fiyatlarıyla izlenir." actions={<Link prefetch={false} href="/portfoylerim/yeni" className={primaryLink}>Yeni portföy</Link>}/>
    {notice.message && <div role="status" className={`mb-5 rounded border px-4 py-3 text-sm ${notice.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: notice.result === "ok" ? "var(--positive)" : "var(--negative)", background: notice.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{notice.message}</div>}
    {!portfolios.ok && <p role="alert" className="mb-4 text-sm text-[var(--negative)]">{portfolios.message}</p>}
    {portfolios.ok && !items.length && <div className="panel-flat"><EmptyState title="Henüz portföyün yok" description="Bir strateji portföyü açıp bileşik sinyali kendi eşiklerinle dene ya da manuel portföyle kendi alım-satımlarını sanal olarak test et."/><div className="flex justify-center pb-6"><Link prefetch={false} href="/portfoylerim/yeni" className={primaryLink}>İlk portföyünü oluştur</Link></div></div>}
    {items.length > 0 && <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{items.map((item) => <Link key={item.id} prefetch={false} href={`/portfoylerim/${item.id}`} className="panel-flat block p-4 transition hover:bg-[var(--surface-hover)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><p className="truncate text-sm font-semibold">{item.name}</p><p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{item.kind === "STRATEGY" ? `Strateji · giriş ${item.config?.entry_score ?? 75} / çıkış ${item.config?.exit_score ?? 55}` : "Manuel"}</p></div>
        <span className={`pill ${item.status === "ACTIVE" ? "pill-positive" : ""}`}>{item.status === "ACTIVE" ? "Aktif" : "Duraklatıldı"}</span>
      </div>
      <p className="mt-4 text-xl font-semibold">{formatMoney(item.total_equity)}</p>
      <p className={`mt-1 text-xs font-medium ${item.total_return_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>{formatPercent(item.total_return_pct, true, 2)} <span className="font-normal text-[var(--text-muted)]">· {formatMoney(item.initial_cash)} başlangıç</span></p>
      <p className="mt-3 text-[11px] text-[var(--text-muted)]">{item.position_count} pozisyon{item.pending_orders ? ` · ${item.pending_orders} bekleyen emir` : ""} · {item.snapshot_date ? `son değerleme ${formatDate(item.snapshot_date)}` : item.started_on ? `ilk işlem günü ${formatDate(item.started_on)}` : "değerleme bekleniyor"}</p>
      {item.last_error && <p className="mt-2 text-[11px] text-[var(--warning)]">Son çalıştırmada hata oluştu</p>}
    </Link>)}</div>}
    <p className="mt-6 text-[11px] leading-5 text-[var(--text-muted)]">Portföyler tamamen sanaldır, gerçek emir iletilmez ve yatırım tavsiyesi değildir. Herkesin görebildiği <Link href="/portfoy" className="text-[var(--primary)]">model portföy</Link> de aynı motorla çalışır.</p>
  </>;
}

function SignedOut() {
  return <div className="mx-auto max-w-2xl py-10">
    <PageHeader eyebrow="Simülasyon · Canlı emir yok" title="Kendi paper portföyünü kur" description="Hesap açarak bileşik sinyali kendi kurallarınla izleyen strateji portföyleri ya da emirlerini kendin verdiğin manuel portföyler oluşturabilirsin."/>
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="panel-flat p-4"><p className="text-sm font-semibold">Strateji portföyü</p><p className="mt-1.5 text-xs leading-5 text-[var(--text-secondary)]">Giriş/çıkış skoru, pozisyon sayısı, zarar-kes ve sektör sınırını sen seç; motor her işlem günü kapanışta alıp satsın.</p></div>
      <div className="panel-flat p-4"><p className="text-sm font-semibold">Manuel portföy</p><p className="mt-1.5 text-xs leading-5 text-[var(--text-secondary)]">Hisse sayfalarından ya da portföyünden sanal alış-satış emri ver; emirler gün sonu fiyatından, komisyonla gerçekleşsin.</p></div>
    </div>
    <div className="mt-6 flex flex-wrap gap-2"><Link prefetch={false} href="/giris?next=/portfoylerim" className={primaryLink}>Giriş yap</Link><Link prefetch={false} href="/kayit" className="pill flex h-9 items-center px-4 hover:text-[var(--text)]">Kayıt ol</Link></div>
  </div>;
}
