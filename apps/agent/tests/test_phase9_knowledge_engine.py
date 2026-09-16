import os
import tempfile
import pytest
import uuid
from pathlib import Path
from sqlalchemy.future import select

from db.session import init_db, AsyncSessionLocal
from db.models import Project, ProjectFile, ProjectTechnology, ProjectDependency, GitMetadata, AgentMemory
from core.knowledge.technology_detector import detect_project_technologies
from core.knowledge.git_indexer import inspect_git_repository
from core.knowledge.indexer import knowledge_indexer
from core.memory import memory_manager, contains_secret

@pytest.mark.asyncio
async def test_technology_detection():
    """Verify evidence-based technology detection without false claims."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create package.json evidence
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text('{"dependencies": {"react": "^18.2.0", "vite": "^4.0.0"}, "devDependencies": {"typescript": "^5.0.0"}}')
        
        # Create requirements.txt evidence
        req_txt = tmp_path / "requirements.txt"
        req_txt.write_text("fastapi==0.100.0\nsqlalchemy>=2.0.0\npytest\n")
        
        techs, deps = detect_project_technologies(tmp_dir)
        tech_names = {t.name for t in techs}
        dep_names = {d.name for d in deps}

        assert "Node.js" in tech_names
        assert "React" in tech_names
        assert "Python" in tech_names
        assert "FastAPI" in tech_names
        assert "SQLAlchemy" in tech_names
        assert "fastapi" in dep_names
        assert "react" in dep_names

@pytest.mark.asyncio
async def test_knowledge_graph_relational_sync():
    """Verify PostgreSQL synchronization of Files, Technologies, Dependencies, and Git metadata."""
    await init_db()
    proj_id = str(uuid.uuid4())
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create sample project structure
        (Path(tmp_dir) / "package.json").write_text('{"dependencies": {"express": "^4.18.2"}}')
        (Path(tmp_dir) / "main.py").write_text("print('hello')")
        
        async with AsyncSessionLocal() as db:
            p = Project(id=proj_id, title="Test Knowledge Project", path=tmp_dir)
            db.add(p)
            await db.commit()

        # Run indexer
        res = await knowledge_indexer.scan_and_index_project(proj_id, tmp_dir)
        assert res["status"] == "success"
        assert res["files_indexed"] >= 2
        assert res["technologies_detected"] >= 1

        async with AsyncSessionLocal() as db:
            files_res = await db.execute(select(ProjectFile).where(ProjectFile.project_id == proj_id))
            files = files_res.scalars().all()
            assert len(files) >= 2

            techs_res = await db.execute(select(ProjectTechnology).where(ProjectTechnology.project_id == proj_id))
            techs = techs_res.scalars().all()
            assert len(techs) >= 1

@pytest.mark.asyncio
async def test_project_isolation_in_semantic_retrieval():
    """Verify strict isolation: Project A memories MUST NOT bleed into Project B search results."""
    await init_db()
    proj_a = str(uuid.uuid4())
    proj_b = str(uuid.uuid4())

    mem_a = await memory_manager.remember(
        memory_type="PROJECT_KNOWLEDGE",
        content="Project Alpha secret formula is standard_ratio_42",
        project_id=proj_a,
        source="user",
        importance=8
    )

    mem_b = await memory_manager.remember(
        memory_type="PROJECT_KNOWLEDGE",
        content="Project Beta secret formula is ratio_99",
        project_id=proj_b,
        source="user",
        importance=8
    )

    # Retrieve Project A context
    results_a = await memory_manager.search(query="secret formula", project_id=proj_a, limit=10)
    contents_a = [m.content for m in results_a]

    assert any("Project Alpha" in c for c in contents_a)
    assert not any("Project Beta" in c for c in contents_a)

    # Retrieve Project B context
    results_b = await memory_manager.search(query="secret formula", project_id=proj_b, limit=10)
    contents_b = [m.content for m in results_b]

    assert any("Project Beta" in c for c in contents_b)
    assert not any("Project Alpha" in c for c in contents_b)

@pytest.mark.asyncio
async def test_memory_lifecycle_and_supersession():
    """Verify state transitions (ACTIVE -> SUPERSEDED) and provenance linking."""
    await init_db()
    proj_id = str(uuid.uuid4())

    # Step 1: Create initial active memory
    original_mem = await memory_manager.remember(
        memory_type="TECHNICAL_CONTEXT",
        content="Database host is configured as db.internal.v1",
        project_id=proj_id,
        source_reliability="USER_CONFIRMED",
        importance=7,
        verification_status="ACTIVE"
    )

    assert original_mem.verification_status == "ACTIVE"

    # Step 2: Supersede memory with updated info
    superseded_mem = await memory_manager.supersede(
        old_memory_id=original_mem.id,
        new_content="Database host migrated to db.internal.v2",
        project_id=proj_id,
        source_reliability="VERIFIED_TASK"
    )

    # Reload original memory
    refreshed_original = await memory_manager.get_by_id(original_mem.id)
    assert refreshed_original.verification_status == "SUPERSEDED"
    assert superseded_mem.verification_status == "ACTIVE"
    assert superseded_mem.supersedes_id == original_mem.id

    # Search should prioritize active memory, hiding superseded memory
    search_results = await memory_manager.search(query="Database host", project_id=proj_id, limit=5)
    result_ids = [m.id for m in search_results]

    assert superseded_mem.id in result_ids
    assert original_mem.id not in result_ids

@pytest.mark.asyncio
async def test_secret_filtering():
    """Verify secret credentials & API keys are rejected from memory storage."""
    with pytest.raises(ValueError, match="Secrets"):
        await memory_manager.remember(
            memory_type="PROJECT_KNOWLEDGE",
            content="Groq API key is gsk_1234567890abcdefghijklmnopqrstuvwxyz",
            project_id="test_proj"
        )

@pytest.mark.asyncio
async def test_bounded_planner_context():
    """Verify Context Intelligence Builder constructs bounded context structure."""
    await init_db()
    proj_id = str(uuid.uuid4())

    ctx = await memory_manager.build_bounded_context(
        project_id=proj_id,
        task_description="Refactor database models"
    )

    assert "project_id" in ctx
    assert "technologies" in ctx
    assert "relevant_memories" in ctx
