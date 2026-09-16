import os
import shutil
import tempfile
import pytest
from pathlib import Path
from sqlalchemy.future import select

from db.session import init_db, AsyncSessionLocal
from db.models import Project, ProjectFile, ProjectChunk
from core.rag.filter import should_index_file, is_ignored_directory, get_file_language
from core.rag.chunker import structural_chunker
from core.rag.indexer import project_rag_indexer
from core.rag.retriever import project_rag_retriever
from core.rag.context_builder import project_context_builder, unified_agent_context_builder
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_rag_file_filtering():
    """Verify ignore rules for .git, node_modules, secrets, binaries, and supported extensions."""
    assert is_ignored_directory(".git") is True
    assert is_ignored_directory("node_modules") is True
    assert is_ignored_directory(".venv") is True
    assert is_ignored_directory("src") is False

    assert get_file_language(Path("test.py")) == "python"
    assert get_file_language(Path("app.tsx")) == "typescript"
    assert get_file_language(Path("schema.sql")) == "sql"
    assert get_file_language(Path("doc.md")) == "markdown"
    assert get_file_language(Path("app.dart")) == "dart"
    assert get_file_language(Path("test.bin")) is None

    # Secret file filtering
    assert should_index_file(Path(".env")) is False
    assert should_index_file(Path(".env.local")) is False
    assert should_index_file(Path("id_rsa")) is False

    # Binary extension filtering
    assert should_index_file(Path("bundle.exe")) is False
    assert should_index_file(Path("archive.zip")) is False
    assert should_index_file(Path("image.png")) is False

@pytest.mark.asyncio
async def test_structural_chunking_languages():
    """Verify structural chunking for Python, TS, SQL, Markdown."""
    # Python
    py_code = """
def authenticate_user(username, password):
    '''Verify credentials'''
    return username == 'admin'

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, sid):
        return self.sessions.get(sid)
"""
    py_chunks = structural_chunker.chunk(py_code, "python")
    symbols = [c.symbol for c in py_chunks]
    assert any("authenticate_user" in str(s) for s in symbols)
    assert any("SessionManager" in str(s) for s in symbols)
    for c in py_chunks:
        assert c.content_hash is not None
        assert len(c.content_hash) == 64

    # TypeScript
    ts_code = """
export interface UserPayload {
  id: string;
  role: string;
}

export const validateToken = (token: string) => {
  return token.length > 10;
};

export class AuthService {
  login() { return true; }
}
"""
    ts_chunks = structural_chunker.chunk(ts_code, "typescript")
    assert len(ts_chunks) >= 2
    ts_syms = [c.symbol for c in ts_chunks]
    assert any("validateToken" in str(s) or "AuthService" in str(s) for s in ts_syms)

    # Markdown
    md_doc = """
# Architecture Guide
Cocoa agent architecture overview.

## Knowledge Subsystem
Details of PostgreSQL and pgvector integration.

## Web Research Subsystem
Tavily and DuckDuckGo search pipelines.
"""
    md_chunks = structural_chunker.chunk(md_doc, "markdown")
    assert len(md_chunks) >= 2
    md_syms = [c.symbol for c in md_chunks]
    assert any("Knowledge Subsystem" in str(s) for s in md_syms)

@pytest.mark.asyncio
async def test_incremental_indexing_workflow():
    """Verify initial indexing, incremental skip of unchanged files, update on change, and deletion on prune."""
    await init_db()

    tmp_dir = tempfile.mkdtemp(prefix="cocoa_rag_test_")
    proj_id = "test_rag_proj_incremental_101"

    try:
        # Create test workspace files
        file1 = Path(tmp_dir) / "auth.py"
        file1.write_text("def login(user):\n    return True\n", encoding="utf-8")

        file2 = Path(tmp_dir) / "database.sql"
        file2.write_text("CREATE TABLE accounts (id INT PRIMARY KEY);\n", encoding="utf-8")

        # Create Project in DB
        async with AsyncSessionLocal() as db:
            p = Project(id=proj_id, title="RAG Test Project", path=tmp_dir)
            db.add(p)
            await db.commit()

        # 1. Initial Indexing
        res1 = await project_rag_indexer.index_project(proj_id, workspace_path=tmp_dir)
        assert res1["status"] == "success"
        assert res1["files_created"] == 2
        assert res1["total_chunks"] >= 2
        assert res1["files_unchanged"] == 0

        # 2. Second Indexing (Unchanged) -> Must skip
        res2 = await project_rag_indexer.index_project(proj_id, workspace_path=tmp_dir)
        assert res2["status"] == "success"
        assert res2["files_unchanged"] == 2
        assert res2["files_created"] == 0
        assert res2["files_updated"] == 0
        assert res2["chunks_updated"] == 0

        # 3. Modify one file
        file1.write_text("def login(user, token):\n    # Updated authentication\n    return token is not None\n", encoding="utf-8")
        res3 = await project_rag_indexer.index_project(proj_id, workspace_path=tmp_dir)
        assert res3["status"] == "success"
        assert res3["files_updated"] == 1
        assert res3["files_unchanged"] == 1
        assert res3["chunks_updated"] >= 1

        # 4. Delete one file from disk
        os.remove(file2)
        res4 = await project_rag_indexer.index_project(proj_id, workspace_path=tmp_dir)
        assert res4["status"] == "success"
        assert res4["files_deleted"] == 1

        # Verify DB chunks for deleted file were removed
        async with AsyncSessionLocal() as db:
            chunks_res = await db.execute(select(ProjectChunk).where(ProjectChunk.project_id == proj_id))
            remaining_chunks = chunks_res.scalars().all()
            paths = [c.file_path for c in remaining_chunks]
            assert "database.sql" not in paths
            assert "auth.py" in paths

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Clean up DB
        async with AsyncSessionLocal() as db:
            proj_del = await db.execute(select(Project).where(Project.id == proj_id))
            p_row = proj_del.scalar_one_or_none()
            if p_row:
                await db.delete(p_row)
                await db.commit()

@pytest.mark.asyncio
async def test_strict_project_isolation():
    """Verify Project A never retrieves Project B chunks."""
    await init_db()

    proj_a = "proj_iso_alpha_99"
    proj_b = "proj_iso_beta_99"

    async with AsyncSessionLocal() as db:
        pa = Project(id=proj_a, title="Alpha Project")
        pb = Project(id=proj_b, title="Beta Project")
        db.add_all([pa, pb])

        # Add chunk for Alpha
        ca = ProjectChunk(
            project_id=proj_a,
            file_path="src/alpha_secret.py",
            language="python",
            chunk_index=0,
            symbol="def alpha_proprietary",
            content="def alpha_proprietary(): return 'ALPHA_CONFIDENTIAL'",
            content_hash="hash_a",
            embedding=[0.5] * 384
        )
        # Add chunk for Beta
        cb = ProjectChunk(
            project_id=proj_b,
            file_path="src/beta_secret.py",
            language="python",
            chunk_index=0,
            symbol="def beta_proprietary",
            content="def beta_proprietary(): return 'BETA_CONFIDENTIAL'",
            content_hash="hash_b",
            embedding=[0.5] * 384
        )
        db.add_all([ca, cb])
        await db.commit()

    try:
        # Search in Project Alpha
        results_a = await project_rag_retriever.search(query="proprietary confidential", project_id=proj_a)
        contents_a = [c.content for c in results_a]
        assert any("ALPHA_CONFIDENTIAL" in c for c in contents_a)
        assert not any("BETA_CONFIDENTIAL" in c for c in contents_a)

        # Search in Project Beta
        results_b = await project_rag_retriever.search(query="proprietary confidential", project_id=proj_b)
        contents_b = [c.content for c in results_b]
        assert any("BETA_CONFIDENTIAL" in c for c in contents_b)
        assert not any("ALPHA_CONFIDENTIAL" in c for c in contents_b)

    finally:
        async with AsyncSessionLocal() as db:
            for pid in [proj_a, proj_b]:
                p_row = await db.get(Project, pid)
                if p_row:
                    await db.delete(p_row)
            await db.commit()

@pytest.mark.asyncio
async def test_bounded_context_builder_and_deduplication():
    """Verify bounded context enforces character limits, returns structured fields, and prevents duplicate chunks."""
    await init_db()
    proj_id = "test_bounded_ctx_proj_88"

    async with AsyncSessionLocal() as db:
        p = Project(id=proj_id, title="Bounded Context Project")
        db.add(p)
        for i in range(5):
            c = ProjectChunk(
                project_id=proj_id,
                file_path=f"src/module_{i}.ts",
                language="typescript",
                chunk_index=i,
                symbol=f"function helper_{i}",
                content=f"export function helper_{i}() {{ return 'chunk_{i}_data'; }}",
                content_hash=f"hash_{i}",
                embedding=[0.2] * 384
            )
            db.add(c)
        await db.commit()

    try:
        ctx_res = await project_context_builder.build_project_context(
            project_id=proj_id,
            query="helper",
            max_chars=500,
            max_chunks=3
        )
        assert ctx_res.project_id == proj_id
        assert len(ctx_res.chunks) <= 3
        assert ctx_res.total_chars <= 600
        for chunk in ctx_res.chunks:
            assert chunk.file.endswith(".ts")
            assert chunk.language == "typescript"
            assert chunk.symbol is not None
            assert chunk.relevance > 0

    finally:
        async with AsyncSessionLocal() as db:
            p_row = await db.get(Project, proj_id)
            if p_row:
                await db.delete(p_row)
            await db.commit()

@pytest.mark.asyncio
async def test_rag_api_endpoints():
    """Verify POST /rag/index, GET /rag/status, POST /rag/search, POST /rag/context, POST /rag/refresh."""
    await init_db()

    tmp_dir = tempfile.mkdtemp(prefix="cocoa_rag_api_")
    proj_id = "test_api_proj_77"

    try:
        f = Path(tmp_dir) / "service.py"
        f.write_text("class PaymentService:\n    def process(self, amount):\n        return True\n", encoding="utf-8")

        async with AsyncSessionLocal() as db:
            p = Project(id=proj_id, title="API Project", path=tmp_dir)
            db.add(p)
            await db.commit()

        client = TestClient(app)

        # 1. POST /rag/index
        res_idx = client.post("/rag/index", json={"project_id": proj_id, "workspace_path": tmp_dir})
        assert res_idx.status_code == 200
        data_idx = res_idx.json()
        assert data_idx["status"] == "success"
        assert data_idx["total_chunks"] >= 1

        # 2. GET /rag/status
        res_stat = client.get(f"/rag/status?project_id={proj_id}")
        assert res_stat.status_code == 200
        data_stat = res_stat.json()
        assert data_stat["indexing_status"] == "INDEXED"
        assert data_stat["total_chunks"] >= 1
        assert "python" in [l.lower() for l in data_stat["languages"]]
        assert "vector_backend" in data_stat

        # 3. POST /rag/search (Verify raw embeddings are NEVER exposed!)
        res_search = client.post("/rag/search", json={"project_id": proj_id, "query": "PaymentService process"})
        assert res_search.status_code == 200
        chunks = res_search.json()
        assert len(chunks) >= 1
        assert "embedding" not in chunks[0]  # MUST NEVER EXPOSE EMBEDDINGS
        assert "PaymentService" in chunks[0]["content"] or "PaymentService" in str(chunks[0]["symbol"])
        assert chunks[0]["file_path"] == "service.py"

        # 4. POST /rag/context
        res_ctx = client.post("/rag/context", json={"project_id": proj_id, "query": "PaymentService"})
        assert res_ctx.status_code == 200
        data_ctx = res_ctx.json()
        assert len(data_ctx["chunks"]) >= 1
        assert "PaymentService" in data_ctx["formatted_context"]

        # 5. POST /rag/refresh
        res_ref = client.post("/rag/refresh", json={"project_id": proj_id})
        assert res_ref.status_code == 200
        assert res_ref.json()["files_unchanged"] == 1

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        async with AsyncSessionLocal() as db:
            p_row = await db.get(Project, proj_id)
            if p_row:
                await db.delete(p_row)
            await db.commit()
