from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from db.models import Base

# Determine database URL
try:
    engine = create_async_engine(settings.postgres_dsn, echo=False, future=True)
except Exception:
    engine = create_async_engine(settings.sqlite_dsn, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    global engine, AsyncSessionLocal
    try:
        # Test postgres connection first
        pg_engine = create_async_engine(settings.postgres_dsn, echo=False, future=True)
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        engine = pg_engine
        AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        print("Connected to PostgreSQL database successfully.")
    except Exception as e:
        print(f"PostgreSQL connection failed ({e}). Using SQLite fallback: {settings.sqlite_dsn}")
        sqlite_engine = create_async_engine(settings.sqlite_dsn, echo=False, future=True)
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        engine = sqlite_engine
        AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
