import pytest
import asyncio
from sqlalchemy.future import select

import db.session as session_module
from db.session import init_db, AsyncSessionLocal
from db.models import AgentMemory, Setting
from core.memory import memory_manager
from core.embeddings import ConfiguredEmbeddingProvider, MockEmbeddingProvider

@pytest.mark.asyncio
async def test_database_connection_and_backend_status():
    await init_db()
    backend = session_module.ACTIVE_DATABASE_BACKEND
    pg_status = session_module.PGVECTOR_STATUS
    assert backend is not None
    assert "PostgreSQL" in backend or "SQLite" in backend
    assert pg_status is not None

@pytest.mark.asyncio
async def test_sqlalchemy_session_commit_and_rollback():
    await init_db()
    
    # 1. Transaction Commit
    async with AsyncSessionLocal() as db:
        test_setting = Setting(key="test_pg_commit_key", value="pg_commit_val")
        db.add(test_setting)
        await db.commit()

    # Verify committed
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Setting).where(Setting.key == "test_pg_commit_key"))
        row = res.scalar_one_or_none()
        assert row is not None
        assert row.value == "pg_commit_val"
        await db.delete(row)
        await db.commit()

    # 2. Transaction Rollback
    async with AsyncSessionLocal() as db:
        rollback_setting = Setting(key="test_pg_rollback_key", value="rollback_val")
        db.add(rollback_setting)
        await db.rollback()

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Setting).where(Setting.key == "test_pg_rollback_key"))
        row = res.scalar_one_or_none()
        assert row is None

@pytest.mark.asyncio
async def test_embedding_provider_abstraction():
    provider = MockEmbeddingProvider(dimension=384)
    vec = await provider.get_embedding("PostgreSQL and pgvector integration")
    assert len(vec) == 384
    assert isinstance(vec[0], float)

    # Empty string safety
    empty_vec = await provider.get_embedding("")
    assert len(empty_vec) == 384

    # Configured provider timeout / fallback
    config_provider = ConfiguredEmbeddingProvider(provider_name="mock")
    config_vec = await config_provider.get_embedding("Test text")
    assert len(config_vec) == 384

@pytest.mark.asyncio
async def test_semantic_search_and_hybrid_retrieval():
    await init_db()
    unique_proj = "proj_semantic_test_unique_99"

    mem1 = await memory_manager.remember(
        memory_type="PROJECT",
        content="This application uses FastAPI for async web routing.",
        project_id=unique_proj,
        importance=8
    )

    mem2 = await memory_manager.remember(
        memory_type="PROJECT",
        content="The frontend is built using Svelte and Vite.",
        project_id=unique_proj,
        importance=6
    )

    # Semantic search query
    results = await memory_manager.search(
        query="fastapi python server routing",
        project_id=unique_proj
    )
    assert len(results) >= 1
    assert "FastAPI" in results[0].content

    # Clean up
    await memory_manager.delete(mem1.id)
    await memory_manager.delete(mem2.id)

@pytest.mark.asyncio
async def test_strict_project_isolation():
    await init_db()

    # Project A Memory
    mem_a = await memory_manager.remember(
        memory_type="PROJECT",
        content="Project Alpha uses PostgreSQL database.",
        project_id="proj_alpha_vector_iso"
    )

    # Project B Memory
    mem_b = await memory_manager.remember(
        memory_type="PROJECT",
        content="Project Beta uses MongoDB database.",
        project_id="proj_beta_vector_iso"
    )

    # Query Project A
    res_a = await memory_manager.search("database", project_id="proj_alpha_vector_iso")
    contents_a = [m.content for m in res_a]
    assert "Project Alpha uses PostgreSQL database." in contents_a
    assert "Project Beta uses MongoDB database." not in contents_a

    # Query Project B
    res_b = await memory_manager.search("database", project_id="proj_beta_vector_iso")
    contents_b = [m.content for m in res_b]
    assert "Project Beta uses MongoDB database." in contents_b
    assert "Project Alpha uses PostgreSQL database." not in contents_b

    # Clean up
    await memory_manager.delete(mem_a.id)
    await memory_manager.delete(mem_b.id)

@pytest.mark.asyncio
async def test_memory_deduplication():
    await init_db()

    content_str = "Deduplication test memory content."
    proj_id = "proj_dedup_test"

    mem_first = await memory_manager.remember(
        memory_type="PROJECT",
        content=content_str,
        project_id=proj_id,
        importance=5
    )

    # Attempt to insert identical memory
    mem_second = await memory_manager.remember(
        memory_type="PROJECT",
        content=content_str,
        project_id=proj_id,
        importance=9
    )

    # Must update existing ID instead of creating new row
    assert mem_second.id == mem_first.id
    assert mem_second.importance == 9

    # Clean up
    await memory_manager.delete(mem_first.id)
