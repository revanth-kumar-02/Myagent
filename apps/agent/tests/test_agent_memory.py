import pytest
from db.session import init_db, AsyncSessionLocal
from db.models import AgentMemory
from core.memory import memory_manager, contains_secret
from sqlalchemy.future import select

@pytest.mark.asyncio
async def test_create_and_retrieve_project_memory():
    await init_db()

    # Create project memory
    mem = await memory_manager.remember(
        memory_type="PROJECT",
        content="This project uses FastAPI and PostgreSQL.",
        project_id="proj_alpha_123",
        importance=8
    )
    assert mem.id is not None
    assert mem.memory_type == "PROJECT"
    assert mem.project_id == "proj_alpha_123"

    # Retrieve relevant memory for proj_alpha_123
    memories = await memory_manager.retrieve(project_id="proj_alpha_123")
    assert len(memories) >= 1
    assert any(m.id == mem.id for m in memories)

    # Cleanup
    await memory_manager.delete(mem.id)

@pytest.mark.asyncio
async def test_project_memory_strict_isolation():
    await init_db()

    # Memory for Project A
    mem_a = await memory_manager.remember(
        memory_type="PROJECT",
        content="Project Alpha uses Redis caching.",
        project_id="proj_alpha_99"
    )

    # Memory for Project B
    mem_b = await memory_manager.remember(
        memory_type="PROJECT",
        content="Project Beta uses MongoDB document store.",
        project_id="proj_beta_99"
    )

    # Query Project A -> MUST NOT include Project B memories
    retrieved_a = await memory_manager.retrieve(project_id="proj_alpha_99")
    retrieved_a_contents = [m.content for m in retrieved_a]
    assert "Project Alpha uses Redis caching." in retrieved_a_contents
    assert "Project Beta uses MongoDB document store." not in retrieved_a_contents

    # Query Project B -> MUST NOT include Project A memories
    retrieved_b = await memory_manager.retrieve(project_id="proj_beta_99")
    retrieved_b_contents = [m.content for m in retrieved_b]
    assert "Project Beta uses MongoDB document store." in retrieved_b_contents
    assert "Project Alpha uses Redis caching." not in retrieved_b_contents

    # Cleanup
    await memory_manager.delete(mem_a.id)
    await memory_manager.delete(mem_b.id)

@pytest.mark.asyncio
async def test_research_memory_with_evidence_and_reject_unsupported():
    await init_db()

    # 1. Valid research memory with evidence -> Accepted
    valid_res = await memory_manager.remember(
        memory_type="RESEARCH",
        content="FastAPI 0.110.0 supports native async lifespan handlers.",
        has_evidence=True
    )
    assert valid_res.id is not None

    # 2. Unsupported research memory without evidence -> Rejected
    with pytest.raises(ValueError, match="Unverified research findings without supporting evidence"):
        await memory_manager.remember(
            memory_type="RESEARCH",
            content="Hallucinated unverified claim about Python 4.0 release date.",
            has_evidence=False
        )

    # Cleanup
    await memory_manager.delete(valid_res.id)

@pytest.mark.asyncio
async def test_prevent_secret_storage_in_memory():
    await init_db()

    # 1. Attempt to store OpenAI / Groq API key in memory -> Rejected
    with pytest.raises(ValueError, match="Secrets, passwords, API keys"):
        await memory_manager.remember(
            memory_type="USER_PREFERENCE",
            content="My secret Groq key is gsk_123456789012345678901234567890"
        )

    # 2. Attempt to store password -> Rejected
    with pytest.raises(ValueError, match="Secrets, passwords, API keys"):
        await memory_manager.remember(
            memory_type="PROJECT",
            content="Database password = SecretPassword123"
        )

@pytest.mark.asyncio
async def test_memory_update_and_delete():
    await init_db()

    mem = await memory_manager.remember(
        memory_type="USER_PREFERENCE",
        content="Prefers dark theme mode.",
        importance=3
    )

    # Update content and importance
    updated = await memory_manager.update(mem.id, content="Prefers high contrast dark mode.", importance=9)
    assert updated.content == "Prefers high contrast dark mode."
    assert updated.importance == 9

    # Delete memory
    deleted = await memory_manager.delete(mem.id)
    assert deleted is True

    # Verify gone from store
    fetched = await memory_manager.store.get_by_id(mem.id)
    assert fetched is None

@pytest.mark.asyncio
async def test_memory_persistence_across_db_reloads():
    await init_db()

    mem = await memory_manager.remember(
        memory_type="PROJECT",
        content="Persistent database schema version v2.4",
        project_id="proj_persist_test"
    )

    # Query directly from a fresh DB session
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AgentMemory).where(AgentMemory.id == mem.id))
        row = res.scalar_one_or_none()
        assert row is not None
        assert row.content == "Persistent database schema version v2.4"

    # Cleanup
    await memory_manager.delete(mem.id)
