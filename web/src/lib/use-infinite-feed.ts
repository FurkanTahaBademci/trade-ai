"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Cursor = Record<string, string | number>;

export function useInfiniteFeed<T>({
  initialItems,
  pageSize,
  endpoint,
  filters,
  cursorFor,
  keyFor,
}: {
  initialItems: T[];
  pageSize: number;
  endpoint: string;
  filters: Record<string, string | undefined>;
  cursorFor: (item: T) => Cursor;
  keyFor: (item: T) => string | number;
}) {
  const [items, setItems] = useState(initialItems);
  const [hasMore, setHasMore] = useState(initialItems.length === pageSize);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(async () => {
    const lastItem = items.at(-1);
    if (!lastItem || !hasMore || loadingRef.current) return;

    loadingRef.current = true;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ limit: String(pageSize) });
    for (const [name, value] of Object.entries(filters)) {
      if (value) params.set(name, value);
    }
    for (const [name, value] of Object.entries(cursorFor(lastItem))) {
      params.set(name, String(value));
    }

    try {
      const response = await fetch(`${endpoint}?${params}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload: unknown = await response.json();
      if (!Array.isArray(payload)) throw new Error("Invalid feed response");
      const nextItems = payload as T[];
      setItems((current) => {
        const knownKeys = new Set(current.map(keyFor));
        return [...current, ...nextItems.filter((item) => !knownKeys.has(keyFor(item)))];
      });
      setHasMore(nextItems.length === pageSize);
    } catch {
      setError("Yeni kayıtlar yüklenemedi. Bağlantıyı kontrol edip tekrar deneyin.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [cursorFor, endpoint, filters, hasMore, items, keyFor, pageSize]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void loadMore();
      },
      { rootMargin: "300px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  return { items, hasMore, loading, error, loadMore, sentinelRef };
}
