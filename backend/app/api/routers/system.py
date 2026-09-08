"""Depolama boyutu izleme (PostgreSQL tablo/veritabani boyutlari).

`/sistem` ekraninda buyuyen tablolari (orn. `kap_attachment`) takip etmek
icin. Kimlik dogrulama gerektirmez — `/health/detailed` gibi operasyonel,
hassas olmayan bilgidir.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/storage")
async def get_storage_report(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    database_size = await db.scalar(text("SELECT pg_database_size(current_database())"))
    result = await db.execute(
        text(
            """
            SELECT relname AS table_name,
                   pg_total_relation_size(relid) AS size_bytes,
                   n_live_tup AS row_estimate
            FROM pg_catalog.pg_stat_user_tables
            ORDER BY size_bytes DESC
            LIMIT 15
            """
        )
    )
    tables = [
        {
            "table": row.table_name,
            "size_bytes": int(row.size_bytes),
            "row_estimate": max(0, int(row.row_estimate)),
        }
        for row in result
    ]
    return {"database_size_bytes": int(database_size or 0), "tables": tables}
