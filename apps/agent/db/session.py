import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from db.models import Base

logger = logging.getLogger(__name__)

from sqlalchemy.pool import NullPool

# Global flags to expose active backend status
IS_POSTGRES_ACTIVE: bool = False
IS_PGVECTOR_AVAILABLE: bool = False
ACTIVE_DATABASE_BACKEND: str = "UNKNOWN"
PGVECTOR_STATUS: str = "NOT CHECKED"

def get_engine():
    if not settings.USE_SQLITE_FALLBACK:
        return create_async_engine(
            settings.postgres_dsn,
            echo=False,
            future=True,
            poolclass=NullPool
        )
    return create_async_engine(settings.sqlite_dsn, echo=False, future=True, poolclass=NullPool)

engine = get_engine()
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    global engine, AsyncSessionLocal, IS_POSTGRES_ACTIVE, IS_PGVECTOR_AVAILABLE, ACTIVE_DATABASE_BACKEND, PGVECTOR_STATUS
    
    if not settings.USE_SQLITE_FALLBACK:
        try:
            logger.info(f"Attempting connection to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}...")
            pg_engine = create_async_engine(
                settings.postgres_dsn,
                echo=False,
                future=True,
                poolclass=NullPool
            )
            
            # 1. Connection Verification
            async with pg_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(Base.metadata.create_all)
                # Safe schema migration for Postgres
                try:
                    await conn.execute(text("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS source_reliability VARCHAR(50) DEFAULT 'USER_CONFIRMED';"))
                except Exception: pass
                try:
                    await conn.execute(text("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0;"))
                except Exception: pass
                try:
                    await conn.execute(text("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50) DEFAULT 'ACTIVE';"))
                except Exception: pass
                try:
                    await conn.execute(text("ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS supersedes_id VARCHAR(36);"))
                except Exception: pass
                try:
                    await conn.execute(text("ALTER TABLE project_files ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);"))
                except Exception: pass
                
            engine = pg_engine
            AsyncSessionLocal.configure(bind=engine)
            IS_POSTGRES_ACTIVE = True
            ACTIVE_DATABASE_BACKEND = f"PostgreSQL (postgresql+asyncpg://{settings.POSTGRES_USER}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB})"
            print(f"[DATABASE] ACTIVE BACKEND: {ACTIVE_DATABASE_BACKEND}")
            logger.info(f"[DATABASE] ACTIVE BACKEND: {ACTIVE_DATABASE_BACKEND}")
            
            # 2. PGVector Verification
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    res = await conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"))
                    row = res.fetchone()
                    if row:
                        IS_PGVECTOR_AVAILABLE = True
                        PGVECTOR_STATUS = f"ENABLED (v{row[1]})"
                        print(f"[DATABASE] PGVECTOR: {PGVECTOR_STATUS}")
                    else:
                        IS_PGVECTOR_AVAILABLE = False
                        PGVECTOR_STATUS = "PGVECTOR NOT AVAILABLE"
                        print(f"[DATABASE] PGVECTOR: {PGVECTOR_STATUS}")
            except Exception as vector_err:
                IS_PGVECTOR_AVAILABLE = False
                PGVECTOR_STATUS = "PGVECTOR HOST DEPENDENCY MISSING: Run 'sudo apt-get install -y postgresql-18-pgvector' or build pgvector from source."
                print(f"[DATABASE] PGVECTOR: {PGVECTOR_STATUS}")
                logger.warning(f"pgvector extension check failed: {vector_err}")
                
            return
            
        except Exception as e:
            error_msg = f"PostgreSQL connection failed to {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}: {e}"
            print(f"[DATABASE ERROR] {error_msg}")
            logger.error(error_msg)
            
            if not settings.USE_SQLITE_FALLBACK:
                # Do NOT silently fallback if PostgreSQL is explicitly configured and fallback disabled
                raise RuntimeError(f"PostgreSQL connection failed and USE_SQLITE_FALLBACK is False: {e}")

    # Fallback to SQLite if USE_SQLITE_FALLBACK is True
    sqlite_engine = create_async_engine(settings.sqlite_dsn, echo=False, future=True)
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe schema migration for SQLite
        columns = [
            ("source_reliability", "VARCHAR(50) DEFAULT 'USER_CONFIRMED'"),
            ("confidence", "FLOAT DEFAULT 1.0"),
            ("verification_status", "VARCHAR(50) DEFAULT 'ACTIVE'"),
            ("supersedes_id", "VARCHAR(36)"),
            ("last_accessed_at", "TIMESTAMP"),
            ("access_count", "INTEGER DEFAULT 0"),
            ("embedding", "JSON")
        ]
        for col_name, col_type in columns:
            try:
                await conn.execute(text(f"ALTER TABLE agent_memories ADD COLUMN {col_name} {col_type};"))
            except Exception: pass
        
        automation_cols = [
            ("workflow_config", "JSON"),
            ("next_run_at", "TIMESTAMP"),
            ("last_run_status", "VARCHAR(50)"),
            ("updated_at", "TIMESTAMP")
        ]
        for col_name, col_type in automation_cols:
            try:
                await conn.execute(text(f"ALTER TABLE automations ADD COLUMN {col_name} {col_type};"))
            except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE project_files ADD COLUMN content_hash VARCHAR(64);"))
        except Exception: pass
    engine = sqlite_engine
    AsyncSessionLocal.configure(bind=engine)
    IS_POSTGRES_ACTIVE = False
    ACTIVE_DATABASE_BACKEND = f"SQLite ({settings.sqlite_dsn})"
    PGVECTOR_STATUS = "BLOCKED (SQLite fallback active)"
    print(f"[DATABASE] ACTIVE BACKEND: {ACTIVE_DATABASE_BACKEND}")
    logger.info(f"[DATABASE] ACTIVE BACKEND: {ACTIVE_DATABASE_BACKEND}")

async def close_db():
    global engine
    if engine:
        await engine.dispose()
        print("[DATABASE] Engine connections gracefully closed.")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
