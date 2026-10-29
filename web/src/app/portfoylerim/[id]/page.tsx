import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { OrderForm } from "@/components/order-form";
import { PaperPortfolioView } from "@/components/paper-portfolio-view";
import { StrategyConfigFields } from "@/components/strategy-config-fields";
import { PageHeader, SectionTitle, ServiceNotice } from "@/components/ui";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import { apiGet } from "@/lib/api";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import { STRATEGY_FIELDS } from "@/lib/paper-forms";
import type { IndexPrice, MyPortfolio, PaperOrder, PaperPosition, PaperRisk, PaperSnapshot, PaperTrade } from "@/lib/types";
import { cancelOrderAction, deletePortfolioAction, updatePortfolioAction } from "../actions";

export const metadata: Metadata = { title: "Portföy", robots: { index: false, follow: false } };

const ORDER_STATUS: Record<PaperOrder["status"], [string, string]> = { PENDING: ["Bekliyor", ""], FILLED: ["Gerçekleşti", "pill-positive"], REJECTED: ["Reddedildi", "pill-negative"], CANCELLED: ["İptal", ""] };

export default async function MyPortfolioPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ result?: string; message?: string }> }) {
  const [{ id }, notice, account, token] = await Promise.all([params, searchParams, currentAccount(), sessionToken()]);
  if (!account || !token) redirect(`/giris?next=/portfoylerim/${encodeURIComponent(id)}`);
  if (!/^\d+$/.test(id)) notFound();
  const base = `/api/me/portfolios/${id}`;
  const portfolio = await accountRequest<MyPortfolio>(base, token);
  if (!portfolio.ok && portfolio.status === 404) notFound();
  if (!portfolio.ok) return <><PageHeader title="Portföy" eyebrow="Portföylerim"/><p role="alert" className="text-sm text-[var(--negative)]">{portfolio.message}</p></>;
  const item = portfolio.data; const manual = item.kind === "MANUAL";
  const [positions, trades, performance, risk, orders] = await Promise.all([
    accountRequest<PaperPosition[]>(`${base}/positions`, token), accountRequest<PaperTrade[]>(`${base}/trades?limit=100`, token), accountRequest<PaperSnapshot[]>(`${base}/performance?limit=365`, token), accountRequest<PaperRisk>(`${base}/risk`, token),
    manual ? accountRequest<PaperOrder[]>(`${base}/orders?limit=50`, token) : Promise.resolve({ ok: true as const, status: 200, data: [] as PaperOrder[] }),
  ]);
  const snapshots = performance.ok ? performance.data : [];
  const earliest = snapshots.map((row) => row.snapshot_date).sort()[0];
  // Endeks herkese açık veridir; paylaşılan önbellekten okunabilir.
  const indexPrices = earliest ? await apiGet<IndexPrice[]>(`/api/index/XU100/prices?start=${earliest}`, [], { revalidate: 300 }) : { data: [] as IndexPrice[], ok: true as const };
  const orderList = orders.ok ? orders.data : [];
  const pending = orderList.filter((order) => order.status === "PENDING");
  const history = orderList.filter((order) => order.status !== "PENDING").slice(0, 15);
  const serviceDown = !positions.ok || !trades.ok || !performance.ok || !risk.ok || !orders.ok;

  return <>
    <PageHeader eyebrow={`${manual ? "Manuel portföy" : "Strateji portföyü"} · Simülasyon`} title={item.name} description={manual ? "Emirlerini sen verirsin; gün sonu kapanış fiyatından, kayma ve komisyonla gerçekleşir." : "Bileşik sinyali aşağıdaki kurallarla her işlem günü kapanışta otomatik izler."} actions={<div className="flex flex-wrap items-center gap-2">
      <span className={`pill ${item.status === "ACTIVE" ? "pill-positive" : ""}`}><span className="h-1.5 w-1.5 rounded-full bg-current"/>{item.status === "ACTIVE" ? "Aktif" : "Duraklatıldı"}</span>
      <form action={updatePortfolioAction}><input type="hidden" name="portfolio_id" value={item.id}/><input type="hidden" name="status" value={item.status === "ACTIVE" ? "PAUSED" : "ACTIVE"}/><button className="pill hover:text-[var(--text)]">{item.status === "ACTIVE" ? "Duraklat" : "Devam ettir"}</button></form>
      <Link prefetch={false} href="/portfoylerim" className="pill hover:text-[var(--text)]">Tüm portföyler</Link>
    </div>}/>
    <ServiceNotice show={serviceDown}/>
    {notice.message && <div role="status" className={`mb-5 rounded border px-4 py-3 text-sm ${notice.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: notice.result === "ok" ? "var(--positive)" : "var(--negative)", background: notice.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{notice.message}</div>}
    {item.last_error && <p role="alert" className="mb-4 rounded border px-4 py-3 text-xs text-[var(--warning)]" style={{ borderColor: "var(--warning)", background: "var(--warning-soft)" }}>Son gün sonu çalıştırmasında hata oluştu; bir sonraki çalıştırmada yeniden denenecek.</p>}
    {!snapshots.length && <p className="mb-4 rounded border px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ borderColor: "var(--border)" }}>İlk gün sonu değerlemesi {item.started_on ? `${formatDate(item.started_on)} ya da sonraki ilk işlem günü` : "ilk işlem günü"} kapanışından sonra (~18:45) yapılır.{manual ? " Emirlerini şimdiden verebilirsin." : " Strateji ilk alımlarını o kapanışta yapar."}</p>}

    {manual && <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(320px,.8fr)_minmax(0,1.2fr)]">
      <section className="panel-flat p-4"><SectionTitle title="Emir ver" subtitle={`${formatMoney(item.cash_balance)} nakit`}/>{item.status === "ACTIVE" ? <OrderForm portfolios={[{ id: item.id, name: item.name, cash: item.cash_balance }]}/> : <p className="text-xs text-[var(--text-muted)]">Duraklatılmış portföye emir verilemez.</p>}</section>
      <section><SectionTitle title="Emirler" subtitle={`${pending.length} bekleyen`}/>{orderList.length ? <div className="table-shell overflow-x-auto"><table className="data-table min-w-[600px]"><thead><tr><th>Hisse</th><th>Yön</th><th>Büyüklük</th><th>Gün</th><th>Durum</th><th/></tr></thead><tbody>{[...pending, ...history].map((order) => <tr key={order.id}>
        <td><Link prefetch={false} href={`/piyasalar/${order.ticker}`} className="font-semibold text-[var(--primary)]">{order.ticker}</Link></td>
        <td className={order.side === "BUY" ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{order.side === "BUY" ? "Alış" : "Satış"}</td>
        <td>{order.quantity != null ? `${formatNumber(order.quantity, 0)} adet` : formatMoney(order.amount ?? 0)}{order.status === "FILLED" && order.filled_quantity != null && <span className="block text-[10px] text-[var(--text-muted)]">{formatNumber(order.filled_quantity, 0)} × {formatMoney(order.fill_price ?? 0)}</span>}</td>
        <td>{formatDate(order.not_before)}</td>
        <td><span className={`pill ${ORDER_STATUS[order.status][1]}`}>{ORDER_STATUS[order.status][0]}</span>{order.note && order.status === "REJECTED" && <span className="mt-1 block max-w-[220px] text-[10px] leading-4 text-[var(--text-muted)]">{order.note}</span>}</td>
        <td className="text-right">{order.status === "PENDING" && <form action={cancelOrderAction}><input type="hidden" name="portfolio_id" value={item.id}/><input type="hidden" name="order_id" value={order.id}/><button className="pill hover:text-[var(--negative)]">İptal</button></form>}</td>
      </tr>)}</tbody></table></div> : <div className="panel-flat p-6 text-center text-xs text-[var(--text-muted)]">Henüz emir yok. Soldaki formdan ya da hisse sayfalarındaki “Paper emri ver” bağlantısından emir verebilirsin.</div>}</section>
    </div>}

    <PaperPortfolioView portfolio={item} positions={positions.ok ? positions.data : []} trades={trades.ok ? trades.data : []} performance={snapshots} risk={risk.ok ? risk.data : null} indexPrices={indexPrices.data} csvHref={`/portfoylerim/${item.id}/islemler.csv`} positionLimit={item.config?.max_positions ?? null} riskNote={manual ? "manuel portföyde otomatik risk kuralı yoktur" : "kurallar aşağıdaki strateji ayarlarındandır"}/>

    {!manual && item.config && <section className="mb-6"><SectionTitle title="Strateji ayarları" subtitle="Değişiklik bir sonraki işlem gününden itibaren geçerlidir"/>
      <dl className="panel-flat grid grid-cols-2 gap-x-6 gap-y-2 p-4 text-[11px] sm:grid-cols-3 xl:grid-cols-4">{STRATEGY_FIELDS.map((field) => <div key={field.key} className="flex justify-between gap-3"><dt className="text-[var(--text-muted)]">{field.label}</dt><dd className="font-medium">{formatNumber(item.config![field.key], field.step < 1 ? 2 : 0)}</dd></div>)}<div className="flex justify-between gap-3"><dt className="text-[var(--text-muted)]">Yeniden dengeleme</dt><dd className="font-medium">{item.config.rebalance_enabled ? "Açık" : "Kapalı"}</dd></div></dl>
      <details className="panel-flat mt-3 p-4"><summary className="cursor-pointer text-xs font-semibold">Ayarları düzenle</summary><form action={updatePortfolioAction} className="mt-4 space-y-4"><input type="hidden" name="portfolio_id" value={item.id}/><input type="hidden" name="has_config" value="1"/><StrategyConfigFields config={item.config}/><button className="h-10 rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Ayarları kaydet</button></form></details>
    </section>}

    <section className="mb-6 grid gap-4 lg:grid-cols-2">
      <details className="panel-flat p-4"><summary className="cursor-pointer text-xs font-semibold">Portföyü yeniden adlandır</summary><form action={updatePortfolioAction} className="mt-4 flex gap-2"><input type="hidden" name="portfolio_id" value={item.id}/><input className="input" name="name" defaultValue={item.name} maxLength={64} required aria-label="Portföy adı"/><button className="pill shrink-0 hover:text-[var(--text)]">Kaydet</button></form></details>
      <details className="panel-flat p-4" style={{ borderColor: "var(--negative)" }}><summary className="cursor-pointer text-xs font-semibold text-[var(--negative)]">Portföyü sil</summary><form action={deletePortfolioAction} className="mt-4 space-y-3"><input type="hidden" name="portfolio_id" value={item.id}/><p className="text-xs leading-5 text-[var(--text-secondary)]">Portföy, tüm işlemleri, emirleri ve geçmiş değerlemeleri kalıcı olarak silinir.</p><label className="flex items-center gap-2 text-xs"><input type="checkbox" name="confirm" required/>Silineceğini anlıyorum.</label><button className="h-9 rounded border px-4 text-xs font-semibold text-[var(--negative)] transition hover:bg-[var(--negative-soft)]" style={{ borderColor: "var(--negative)" }}>Kalıcı olarak sil</button></form></details>
    </section>
    <p className="text-[11px] leading-5 text-[var(--text-muted)]">Başlangıç {formatMoney(item.initial_cash)} · ilk işlem günü {item.started_on ? formatDate(item.started_on) : "—"}. Bu portföy tamamen sanaldır; gerçek emir göndermez, yatırım tavsiyesi değildir.</p>
  </>;
}
