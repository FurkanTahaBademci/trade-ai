"""PostgreSQL depolama temizligi ve vakumlama scripti.

Kullanim:
    python backend/scripts/vacuum_storage.py
    # veya Docker container icinde:
    docker compose exec api python scripts/vacuum_storage.py
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.core.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("vacuum_storage")


async def vacuum_storage() -> dict:
    log.info("Depolama vakumlama ve temizlik islemi baslatiliyor...")
    async with engine.connect() as conn:
        autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        dialect = engine.dialect.name

        if dialect == "postgresql":
            size_before = await autocommit_conn.scalar(
                text("SELECT pg_database_size(current_database())")
            )
            size_before_mb = (size_before or 0) / (1024 * 1024)
            log.info("Baslangic veritabani boyutu: %.2f MB", size_before_mb)

            try:
                table_size_before = await autocommit_conn.scalar(
                    text("SELECT pg_size_pretty(pg_total_relation_size('kap_attachment'))")
                )
                log.info("   'kap_attachment' tablosunun baslangic boyutu: %s", table_size_before)
            except Exception as exc:
                log.debug("kap_attachment tablosu kontrol edilemedi: %s", exc)

            log.info("1. 'kap_attachment' tablosu vakumlanip disk alani serbest birakiliyor...")
            try:
                await autocommit_conn.execute(text("VACUUM FULL kap_attachment"))
                log.info("   'kap_attachment' tablosu basariyla sikistirildi.")
            except Exception as exc:
                log.warning("   'kap_attachment' tablosu vakumlanamadi: %s", exc)

            log.info("2. Tum veritabani istatistikleri guncellenip vakumlaniyor (VACUUM ANALYZE)...")
            await autocommit_conn.execute(text("VACUUM ANALYZE"))

            size_after = await autocommit_conn.scalar(
                text("SELECT pg_database_size(current_database())")
            )
            size_after_mb = (size_after or 0) / (1024 * 1024)
            freed_bytes = max(0, (size_before or 0) - (size_after or 0))
            freed_mb = freed_bytes / (1024 * 1024)

            try:
                table_size_after = await autocommit_conn.scalar(
                    text("SELECT pg_size_pretty(pg_total_relation_size('kap_attachment'))")
                )
                log.info("   'kap_attachment' tablosunun sikistirma sonrasi boyutu: %s", table_size_after)
            except Exception:
                pass

            log.info("Temizlik sonrasi veritabani boyutu: %.2f MB", size_after_mb)
            log.info("Geri kazanilan disk alani: %.2f MB", freed_mb)

            return {
                "ok": True,
                "size_before_bytes": size_before,
                "size_after_bytes": size_after,
                "freed_bytes": freed_bytes,
                "freed_mb": freed_mb,
            }
        else:
            log.info("SQLite veya farkli motor algilandi (%s), VACUUM calistiriliyor...", dialect)
            await autocommit_conn.execute(text("VACUUM"))
            log.info("Vakumlama tamamlandi.")
            return {"ok": True, "dialect": dialect}


def main() -> None:
    try:
        asyncio.run(vacuum_storage())
    except Exception as exc:
        log.warning("Depolama vakumlama sirasinda hata olustu (atlaniliyor): %s", exc)


if __name__ == "__main__":
    main()
