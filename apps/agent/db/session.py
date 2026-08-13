from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from db.models import Base

def get_engine():
    if settings.USE_SQLITE_FALLBACK:
        return create_async_engine(settings.sqlite_dsn, echo=False, future=True)
    try:
        return create_async_engine(settings.postgres_dsn, echo=False, future=True)
    except Exception:
        return create_async_engine(settings.sqlite_dsn, echo=False, future=True)

engine = get_engine()
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    global engine, AsyncSessionLocal
    try:
        if not settings.USE_SQLITE_FALLBACK:
            pg_engine = create_async_engine(settings.postgres_dsn, echo=False, future=True)
            async with pg_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            engine = pg_engine
            AsyncSessionLocal.configure(bind=engine)
            print("Connected to PostgreSQL database successfully.")
            return
    except Exception as e:
        print(f"PostgreSQL connection failed ({e}). Using SQLite fallback: {settings.sqlite_dsn}")

    sqlite_engine = create_async_engine(settings.sqlite_dsn, echo=False, future=True)
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    engine = sqlite_engine
    AsyncSessionLocal.configure(bind=engine)
    print(f"Connected to SQLite database: {settings.sqlite_dsn}")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
