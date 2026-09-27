import type { AIBriefingData } from "@/lib/types";
import { Icon } from "./icon";
import { TickerPills } from "./ui";

export function MarketBriefing({ briefing }: { briefing: AIBriefingData | null }) {
  if (!briefing) return null;

  const isBullish = briefing.market_mood === "BULLISH";
  const isBearish = briefing.market_mood === "BEARISH";

  return (
    <section className="panel mb-7 overflow-hidden border border-[var(--border)] shadow-xs">
      {/* Üst Başlık Şeridi */}
      <div className="flex flex-col gap-3 border-b border-[var(--border-subtle)] bg-[var(--surface-raised)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-[12px] bg-[var(--primary-soft)] text-[var(--primary)]">
            <Icon name="spark" size={20} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow">Otomatik Veri Özeti</span>
              <span className="pill pill-primary text-[10px] font-semibold">
                {briefing.session} BÜLTENİ
              </span>
              <span
                className={`pill text-[10px] font-semibold ${
                  isBullish
                    ? "pill-positive"
                    : isBearish
                    ? "pill-negative"
                    : ""
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {isBullish
                  ? "Pozitif Skor Görünümü"
                  : isBearish
                  ? "Negatif Skor Görünümü"
                  : "Nötr / Yetersiz Veri"}
              </span>
            </div>
            <h2 className="mt-1 text-base font-semibold tracking-[-0.02em] text-[var(--text)] sm:text-lg">
              {briefing.headline}
            </h2>
          </div>
        </div>

        <span className="text-right text-[11px] text-[var(--text-muted)]">
          {new Date(briefing.generated_at).toLocaleTimeString("tr-TR", {
            hour: "2-digit",
            minute: "2-digit",
          })}{" "}
          güncellendi
        </span>
      </div>

      <div className="p-5 sm:p-6">
        {/* Yönetici Özeti */}
        <p className="text-sm leading-7 text-[var(--text-secondary)]">
          {briefing.summary}
        </p>

        {/* Günün Kritik Katalizörleri */}
        {briefing.catalysts && briefing.catalysts.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Son Haberler ve KAP Değerlendirmeleri
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {briefing.catalysts.map((cat, idx) => (
                <div
                  key={idx}
                  className="flex flex-col justify-between rounded-[12px] border border-[var(--border)] bg-[var(--surface-raised)] p-3.5 transition hover:border-[var(--border-strong)]"
                >
                  <div>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                        {cat.category}
                      </span>
                      <span
                        className={`pill text-[10px] font-semibold ${
                          cat.impact === "POSITIVE"
                            ? "pill-positive"
                            : cat.impact === "NEGATIVE"
                            ? "pill-negative"
                            : ""
                        }`}
                      >
                        {cat.impact === "POSITIVE"
                          ? "Pozitif"
                          : cat.impact === "NEGATIVE"
                          ? "Negatif"
                          : "Nötr"}
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs font-semibold leading-snug text-[var(--text)]">
                      {cat.title}
                    </p>
                    <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-[var(--text-muted)]">
                      {cat.description}
                    </p>
                  </div>
                  {cat.tickers && cat.tickers.length > 0 && (
                    <div className="mt-3 border-t border-[var(--border-subtle)] pt-2">
                      <TickerPills tickers={cat.tickers} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sektörel Görünüm ve Aksiyon Notları */}
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {/* Sektör Notları */}
          {briefing.sector_commentary && briefing.sector_commentary.length > 0 && (
            <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface-raised)] p-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Öne Çıkan Sektör Dinamikleri
              </h3>
              <div className="space-y-2.5">
                {briefing.sector_commentary.map((sec, idx) => (
                  <div key={idx} className="flex items-start justify-between gap-3 text-xs">
                    <div>
                      <span className="font-semibold text-[var(--text)]">{sec.sector}:</span>{" "}
                      <span className="text-[var(--text-secondary)]">{sec.comment}</span>
                    </div>
                    <span className="shrink-0 pill text-[10px] font-medium">
                      {sec.trend}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Aksiyon Notları */}
          {briefing.actionable_takeaways && briefing.actionable_takeaways.length > 0 && (
            <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface-raised)] p-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Takip Edilecek Seviye ve Çıkarımlar
              </h3>
              <ul className="space-y-2 text-xs text-[var(--text-secondary)]">
                {briefing.actionable_takeaways.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="mt-0.5 text-[var(--primary)]">✓</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <div
        className="border-t px-5 py-2.5 text-[11px] text-[var(--text-muted)]"
        style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
      >
        Son 24 saatteki haberler, tamamlanan KAP analizleri ve hesaplanan bileşik skorlar ile son kayıtlı faiz kararından derlenmiştir. Yatırım tavsiyesi içermez.
      </div>
    </section>
  );
}
