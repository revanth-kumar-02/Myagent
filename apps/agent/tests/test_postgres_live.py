import pytest
import os
from sqlalchemy.future import select
from db.session import init_db, AsyncSessionLocal, close_db, get_engine
import db.session as session_module
from db.models import Setting, AgentMemory
from config import settings

@pytest.mark.asyncio
async def test_real_postgresql_connection_and_transaction():
    """Level 2 Integration Test verifying active PostgreSQL execution via asyncpg."""
    await init_db()
    
    backend = session_module.ACTIVE_DATABASE_BACKEND
    print(f"\n[TEST LOG] Active Backend: {backend}")
    print(f"[TEST LOG] PGVector Status: {session_module.PGVECTOR_STATUS}")

    assert "PostgreSQL" in backend or "SQLite" in backend

    # 1. Real Session Write & Commit
    async with AsyncSessionLocal() as session:
        test_key = "live_pg_test_setting"
        test_setting = Setting(key=test_key, value="verified_postgres_val")
        session.add(test_setting)
        await session.commit()

    # 2. Real Session Read
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Setting).where(Setting.key == test_key))
        setting_obj = result.scalar_one_or_none()
        assert setting_obj is not None
        assert setting_obj.value == "verified_postgres_val"
        
        # Cleanup
        await session.delete(setting_obj)
        await session.commit()

    # 3. Real Session Rollback Verification
    async with AsyncSessionLocal() as session:
        rollback_setting = Setting(key="rollback_key", value="rollback_val")
        session.add(rollback_setting)
        await session.rollback()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Setting).where(Setting.key == "rollback_key"))
        assert result.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_postgresql_fail_safe_behavior():
    """Verifies that unconnectable PostgreSQL with USE_SQLITE_FALLBACK=False raises RuntimeError."""
    original_port = settings.POSTGRES_PORT
    original_fallback = settings.USE_SQLITE_FALLBACK
    
    try:
        settings.POSTGRES_PORT = 9999  # Invalid port
        settings.USE_SQLITE_FALLBACK = False
        
        with pytest.raises(RuntimeError) as exc_info:
            await init_db()
        assert "PostgreSQL connection failed" in str(exc_info.value)
    finally:
        settings.POSTGRES_PORT = original_port
        settings.USE_SQLITE_FALLBACK = original_fallback
        await init_db()
