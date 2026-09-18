"""
db.client — Async database client

Provides:
  - Async SQLAlchemy engine + session factory
  - Redis connection pool
  - Lifecycle helpers (startup / shutdown)
"""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings

# ── PostgreSQL ────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.debug,
    # NullPool avoids connection-pool issues when running under uvicorn workers
    poolclass=NullPool if settings.workers > 1 else None,  # type: ignore[arg-type]
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionFactory() as session:
        yield session


# ── Redis ─────────────────────────────────────────────────────────────────────

redis_pool = aioredis.ConnectionPool.from_url(
    settings.redis_url,
    max_connections=20,
    decode_responses=True,
)


def get_redis() -> aioredis.Redis:
    """Returns a Redis client backed by the shared pool."""
    return aioredis.Redis(connection_pool=redis_pool)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def startup() -> None:
    """Called on application startup — verify connectivity."""
    # Verify PostgreSQL
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

    # Verify Redis
    r = get_redis()
    await r.ping()
    await r.aclose()


async def shutdown() -> None:
    """Called on application shutdown — dispose connections."""
    await engine.dispose()
    await redis_pool.aclose()
