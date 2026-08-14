import asyncio
from db.session import (
    init_db,
    close_db,
    IS_POSTGRES_ACTIVE,
    IS_PGVECTOR_AVAILABLE,
    ACTIVE_DATABASE_BACKEND,
    PGVECTOR_STATUS
)
from core.memory import memory_manager, MemoryManager, MemoryStore

async def main():
    print("==================================================")
    print("🚀 BATCH 4A REAL APPLICATION-LEVEL SMOKE TEST")
    print("==================================================")

    # 1. Start Cocoa Backend DB initialization
    await init_db()

    # 2. Verify backend active database report
    print(f"📊 ACTIVE BACKEND: {ACTIVE_DATABASE_BACKEND}")
    print(f"📊 PGVECTOR STATUS: {PGVECTOR_STATUS}")

    # 3. Create a memory for Project A
    proj_a = "proj_smoke_4a_alpha"
    proj_b = "proj_smoke_4a_beta"

    mem_a = await memory_manager.remember(
        memory_type="PROJECT",
        content="Project Alpha backend is built using PostgreSQL with asyncpg connection pooling.",
        project_id=proj_a,
        importance=9
    )
    print(f"✅ Created Memory ID '{mem_a.id}' for Project A ('{proj_a}')")

    # 4. Restart backend simulation (Dispose connection pool and re-init)
    await close_db()
    print("🔄 Simulated backend restart / pool reset...")
    await init_db()

    # 5. Retrieve memory for Project A after restart
    restarted_memory_manager = MemoryManager(store=MemoryStore())
    retrieved_a = await restarted_memory_manager.retrieve(project_id=proj_a)
    assert len(retrieved_a) > 0
    print(f"✅ Retrieved {len(retrieved_a)} memory records for Project A after restart!")

    # 6. Perform semantic search
    semantic_results = await restarted_memory_manager.search(
        query="postgresql asyncpg connection pool",
        project_id=proj_a
    )
    assert len(semantic_results) > 0
    print(f"✅ Semantic search returned top match: '{semantic_results[0].content}'")
    assert "PostgreSQL with asyncpg" in semantic_results[0].content

    # 7. Verify Project B CANNOT retrieve Project A memory (Strict Isolation)
    retrieved_b = await restarted_memory_manager.search(
        query="postgresql asyncpg",
        project_id=proj_b
    )
    b_contents = [m.content for m in retrieved_b]
    assert "Project Alpha backend is built using PostgreSQL with asyncpg connection pooling." not in b_contents
    print("✅ Strict Project Isolation Verified: Project B cannot retrieve Project A memory!")

    # Cleanup
    await restarted_memory_manager.delete(mem_a.id)

    print("==================================================")
    print("🎉 BATCH 4A SMOKE TEST COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
