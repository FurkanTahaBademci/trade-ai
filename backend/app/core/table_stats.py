"""Buyuk tablolarda tam tarama yapmadan satir sayisi ve deger dagilimi.

`count(*)` PostgreSQL'de tum tabloyu (veya indeksi) okur; haber, KAP ve LLM
tablolari buyudukce her dakika cagrilan sayaclar pahalilasir. Burada planlayicinin
kullandigi istatistikler okunur:

- Satir tahmini: `pg_class.reltuples / relpages` (son ANALYZE'daki yogunluk)
  x tablonun bugunku sayfa sayisi. Son ANALYZE'dan sonraki eklemeleri de izler.
- Deger dagilimi: `pg_stats.most_common_vals/most_common_freqs` x satir tahmini.

Tablo kucukken (EXACT_COUNT_LIMIT alti) kesin sayim zaten ucuzdur ve kucuk
kurulumlarda sayilarin birebir dogru gorunmesi icin kesin deger kullanilir.
"""

from __future__ import annotations

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession

EXACT_COUNT_LIMIT = 100_000

_ESTIMATE_SQL = text(
    """
    SELECT CASE
             WHEN c.reltuples < 0 OR c.relpages = 0 THEN NULL
             ELSE c.reltuples / c.relpages
                  * (pg_relation_size(c.oid) / current_setting('block_size')::int)
           END
    FROM pg_class c
    WHERE c.oid = to_regclass(:table)
    """
)
_FREQUENCY_SQL = text(
    """
    SELECT most_common_vals::text::text[] AS vals, most_common_freqs AS freqs
    FROM pg_stats
    WHERE schemaname = current_schema() AND tablename = :table AND attname = :column
    """
)


async def estimated_rows(db: AsyncSession, table: str) -> int | None:
    """Planlayici istatistiginden satir tahmini; tablo hic analiz edilmediyse None."""
    value = (await db.execute(_ESTIMATE_SQL, {"table": table})).scalar()
    return max(0, round(value)) if value is not None else None


async def value_frequencies(db: AsyncSession, table: str, column: str) -> dict[str, float]:
    """Kolonun en sik degerleri ve oranlari (ornek: {'news': 0.62, 'kap': 0.38})."""
    row = (await db.execute(_FREQUENCY_SQL, {"table": table, "column": column})).first()
    if row is None or row.vals is None:
        return {}
    return {str(value): float(freq) for value, freq in zip(row.vals, row.freqs, strict=False)}


async def fast_count(db: AsyncSession, table: str, exact: Select) -> tuple[int, bool]:
    """(sayi, tahmini_mi). Kucuk tabloda `exact` sorgusu calisir."""
    estimate = await estimated_rows(db, table)
    if estimate is None or estimate < EXACT_COUNT_LIMIT:
        return int(await db.scalar(exact) or 0), False
    return estimate, True


async def fast_grouped_count(
    db: AsyncSession, table: str, column: str, exact: Select, *, total: int, estimated: bool
) -> dict[str, int]:
    """Kolon degerlerine gore sayim. `estimated` ise (buyuk tablo) dagilim
    istatistigi `total` ile carpilir; degilse `exact` (GROUP BY) sorgusu calisir."""
    if not estimated:
        return {str(key): int(count) for key, count in (await db.execute(exact)).all()}
    frequencies = await value_frequencies(db, table, column)
    return {value: round(total * freq) for value, freq in frequencies.items() if freq > 0}
