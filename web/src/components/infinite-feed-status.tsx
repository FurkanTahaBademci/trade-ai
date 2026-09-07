import type { RefObject } from "react";

export function InfiniteFeedStatus({
  sentinelRef,
  loading,
  error,
  hasMore,
  onRetry,
  endLabel = "Tüm kayıtları gördünüz.",
}: {
  sentinelRef: RefObject<HTMLDivElement | null>;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  onRetry: () => void;
  endLabel?: string;
}) {
  return <div ref={sentinelRef} className="flex min-h-24 items-center justify-center py-6">
    {error ? <div className="text-center"><p className="text-xs text-[var(--negative)]">{error}</p><button type="button" onClick={onRetry} className="mt-3 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--surface-hover)]">Tekrar dene</button></div>
      : loading ? <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--primary)]"/>Kayıtlar yükleniyor</div>
      : !hasMore ? <p className="text-xs text-[var(--text-muted)]">{endLabel}</p>
      : <span className="sr-only">Daha fazla kayıt için aşağı kaydırın</span>}
  </div>;
}
