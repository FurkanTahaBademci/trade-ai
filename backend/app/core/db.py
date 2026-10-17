"""Async SQLAlchemy engine/session kurulumu.

Kullanim (FastAPI endpoint icinde):

    from app.core.db import get_db

    @router.get(...)
    async def handler(db: AsyncSession = Depends(get_db)):
        ...

Collector/worker kodunda ise `async with session_factory() as session:` kullan.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    **(
        {"pool_size": settings.db_pool_size, "max_overflow": settings.db_max_overflow}
        if not settings.database_url.startswith("sqlite")
        else {}
    ),
)

session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Tum SQLAlchemy modelleri bundan turer (app/models/*)."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


async def ping_db() -> bool:
    """Health check icin: DB'ye basit bir SELECT 1 atar."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
