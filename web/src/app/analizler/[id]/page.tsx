import type { Metadata } from "next";
import { cache } from "react";
import { notFound } from "next/navigation";
import { apiGet, isApiNotFound } from "@/lib/api";
import type { Evaluation } from "@/lib/types";
import { eventName, formatDate, formatNumber, formatPercent, sourceName } from "@/lib/format";
import { isAdminViewer } from "@/lib/admin-viewer";
import { pageTitle } from "@/lib/page-title";
import { Breadcrumbs, EmptyState, ScoreMeter, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";
import Link from "next/link";
import { evaluationSourceHref, tierLabel } from "@/components/source-analysis";

const loadEvaluation = cache((id: string) => apiGet<Evaluation | null>(`/api/evaluations/${id}`, null));

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const item = (await loadEvaluation(id)).data;
  return { title: pageTitle(item?.summary, "AI Analiz Detayı") };
}

const HORIZONS: Record<string, string> = { intraday: "Gün içi", short: "Kısa vade", medium: "Orta vade", long: "Uzun vade", unclear: "Belirsiz" };
const STATUSES: Record<string, string> = { succeeded: "Tamamlandı", failed: "Başarısız", running: "İşleniyor", filtered: "Ön filtrede elendi" };

function sentimentText(score: number | null) {
  if (score == null) return "—";
  const tone = score >= 0.2 ? "Olumlu" : score <= -0.2 ? "Olumsuz" : "Nötr";
  return `${tone} (${formatNumber(score, 2)})`;
}

export default async function AnalysisDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [result, admin] = await Promise.all([loadEvaluation(id), isAdminViewer()]); const item = result.data;
  if (isApiNotFound(result)) notFound();
  if (!item) return <div className="panel-flat"><EmptyState title="Analiz bulunamadı"/></div>;
  return <><Breadcrumbs items={[{ label: "AI Analizleri", href: "/analizler" }, { label: `#${item.id}` }]}/><div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><div className="mb-3 flex flex-wrap gap-2"><span className="pill">{sourceName(item.source_type)}</span><span className="pill pill-primary">{eventName(item.event_type)}</span><span className="pill" title={item.tier >= 2 ? "Daha güçlü modelle yapılan ikinci, ayrıntılı inceleme" : "İçeriğin önemini ölçen hızlı ilk inceleme"}>{tierLabel(item.tier)}</span><Link href={evaluationSourceHref(item)} className="pill transition hover:text-[var(--primary)]">Kaynağı aç <Icon name="arrow" size={12}/></Link></div><h1 className="break-words text-2xl font-semibold leading-tight tracking-[-0.035em] sm:text-3xl">{item.summary || (item.status === "failed" ? "AI değerlendirmesi başarısız" : "AI değerlendirmesi")}</h1><div className="mt-4"><TickerPills tickers={item.ticker_codes}/></div></div><div className="flex gap-3"><ScoreMeter score={item.relevance_score} label="İlgi"/><ScoreMeter score={item.impact_score} label="Etki"/></div></div>{item.status === "failed" && <div className="mb-6 rounded border border-[var(--negative)] bg-[var(--negative-soft)] px-4 py-3 text-sm text-[var(--negative)]"><p className="font-semibold">Analiz tamamlanamadı</p><p className="mt-1 break-words text-xs leading-5">{admin && item.error_text ? item.error_text : "Sistem bu içeriği daha sonra yeniden değerlendirmeyi deneyecek."}</p></div>}<div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]"><div className="min-w-0 space-y-4"><section className="panel-flat p-4 sm:p-5"><p className="eyebrow mb-3">Değerlendirme gerekçesi</p><p className="whitespace-pre-wrap break-words text-sm leading-7 text-[var(--text-secondary)]">{item.rationale || "Bu değerlendirme için ayrıntılı gerekçe bulunmuyor."}</p></section>{admin && item.result && <details className="panel-flat p-4 sm:p-5"><summary className="eyebrow">Yapılandırılmış çıktı (yönetici)</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-[var(--text-secondary)]">{JSON.stringify(item.result, null, 2)}</pre></details>}</div><aside className="panel-flat h-fit p-5"><h2 className="text-sm font-semibold">Analiz bilgileri</h2><dl className="mt-4 space-y-4"><Info label="Güven" value={item.confidence == null ? "—" : formatPercent(item.confidence * 100)}/><Info label="Duygu" value={sentimentText(item.sentiment_score)}/><Info label="Zaman ufku" value={item.time_horizon ? HORIZONS[item.time_horizon] ?? item.time_horizon : "—"}/><Info label="Oluşturuldu" value={formatDate(item.created_at, true)}/></dl>{admin && <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--border)" }}><p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"><Icon name="lock" size={12}/>Yönetici ayrıntıları</p><dl className="mt-3 space-y-3"><Info label="Durum" value={STATUSES[item.status] ?? item.status}/><Info label="Deneme" value={String(item.attempt_count)}/><Info label="Model" value={item.model}/><Info label="API" value={item.api_mode === "interactions" ? "Interactions · SSE" : "GenerateContent"}/><Info label="Token" value={formatNumber(item.total_tokens, 0)}/><Info label="Gecikme" value={item.latency_ms ? `${formatNumber(item.latency_ms, 0)} ms` : "—"}/></dl></div>}<div className="mt-5 flex gap-2 border-t pt-4 text-[11px] leading-5 text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}><Icon name="activity" size={14} className="mt-0.5 shrink-0"/>Bu içerik yapay zekâ tarafından otomatik üretilmiştir ve yatırım tavsiyesi değildir.</div></aside></div></>;
}
function Info({ label, value }: { label: string; value: string }) { return <div><dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{label}</dt><dd className="mt-1 break-words text-xs font-medium text-[var(--text-secondary)]">{value}</dd></div>; }
