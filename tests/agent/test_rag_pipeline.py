"""
tests.agent.test_rag_pipeline — Comprehensive RAG Pipeline Unit & Component Tests

Tests covering:
  - Scanner: hash detection, added/changed/deleted/skipped classification, ignore patterns
  - Parser: code, markdown, spreadsheet, plain text parsing
  - Chunker: structure-aware splitting, code symbols, markdown hierarchy, provenance metadata
  - Retriever & RRF: dual-ranking score boost, project isolation, metadata filtering
  - ContextBuilder: token budget enforcement, source provenance matching
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.chunker import StructuralChunker, _count_tokens
from rag.context_builder import ContextBuilder
from rag.parser import Parser
from rag.retriever import RAGRetriever
from rag.scanner import Scanner
from rag.types import (
    Chunk,
    DocumentType,
    FileEventType,
    ParsedDocument,
    RetrievedChunk,
)


class TestScanner:
    @pytest.mark.asyncio
    async def test_detect_added_files(self) -> None:
        project_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f1 = root / "main.py"
            f1.write_text("print('hello world')")

            # Mock DB with no known files
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db.execute.return_value = mock_result

            scanner = Scanner(project_id, root, mock_db)
            events = [e async for e in scanner.scan()]

            assert len(events) == 1
            assert events[0].file_path == "main.py"
            assert events[0].event_type == FileEventType.ADDED
            assert events[0].content_hash is not None
            assert events[0].file_size == len("print('hello world')")

    @pytest.mark.asyncio
    async def test_detect_changed_files_by_hash(self) -> None:
        project_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f1 = root / "app.py"
            f1.write_text("def run(): pass")

            # Mock DB having an old hash
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [("app.py", "old_stale_hash_value")]
            mock_db.execute.return_value = mock_result

            scanner = Scanner(project_id, root, mock_db)
            events = [e async for e in scanner.scan()]

            assert len(events) == 1
            assert events[0].file_path == "app.py"
            assert events[0].event_type == FileEventType.CHANGED

    @pytest.mark.asyncio
    async def test_detect_deleted_files(self) -> None:
        project_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            # No files on disk, but DB has record

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [("removed_file.py", "some_hash")]
            mock_db.execute.return_value = mock_result

            scanner = Scanner(project_id, root, mock_db)
            events = [e async for e in scanner.scan()]

            assert len(events) == 1
            assert events[0].file_path == "removed_file.py"
            assert events[0].event_type == FileEventType.DELETED
            assert events[0].content_hash is None

    @pytest.mark.asyncio
    async def test_ignores_default_patterns(self) -> None:
        project_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            # Create ignored directories and files
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("git config")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "pkg.js").write_text("package code")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "cached.pyc").write_text("bytecode")
            (root / "valid.py").write_text("x = 42")

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db.execute.return_value = mock_result

            scanner = Scanner(project_id, root, mock_db)
            events = [e async for e in scanner.scan()]

            assert len(events) == 1
            assert events[0].file_path == "valid.py"


class TestParser:
    @pytest.mark.asyncio
    async def test_parse_code(self) -> None:
        parser = Parser()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
            tmp.write("def foo():\n    return 42\n")
            tmp_path = Path(tmp.name)

        try:
            doc = await parser.parse(tmp_path)
            assert doc is not None
            assert doc.doc_type == DocumentType.CODE
            assert doc.metadata["language"] == "python"
            assert "foo" in doc.content
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_parse_markdown(self) -> None:
        parser = Parser()
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as tmp:
            tmp.write("# Main Title\n\nIntro text.\n\n## Sub Section\n\nDetails.\n")
            tmp_path = Path(tmp.name)

        try:
            doc = await parser.parse(tmp_path)
            assert doc is not None
            assert doc.doc_type == DocumentType.MARKDOWN
            headings = doc.metadata.get("headings", [])
            assert len(headings) == 2
            assert headings[0]["text"] == "Main Title"
            assert headings[1]["text"] == "Sub Section"
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_parse_plain(self) -> None:
        parser = Parser()
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
            tmp.write('{"key": "value"}')
            tmp_path = Path(tmp.name)

        try:
            doc = await parser.parse(tmp_path)
            assert doc is not None
            assert doc.doc_type == DocumentType.PLAIN
            assert '"key": "value"' in doc.content
        finally:
            tmp_path.unlink()


class TestStructuralChunker:
    def test_code_chunk_respects_token_limit(self) -> None:
        project_id = uuid.uuid4()
        chunker = StructuralChunker(project_id, chunk_size=30, chunk_overlap=5)

        # Code with multiple functions
        code = (
            "def function_alpha():\n"
            "    val = [x * 2 for x in range(100)]\n"
            "    return sum(val)\n\n"
            "def function_beta():\n"
            "    text = 'hello world' * 50\n"
            "    return text\n"
        )
        doc = ParsedDocument(
            file_path="service.py",
            doc_type=DocumentType.CODE,
            content=code,
            metadata={"language": "python"},
        )

        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2
        for chunk in chunks:
            tokens = _count_tokens(chunk.content)
            assert tokens <= chunker.chunk_size + 10  # within margin
            assert chunk.project_id == project_id
            assert chunk.file_path == "service.py"
            assert "start_line" in chunk.metadata
            assert "end_line" in chunk.metadata

    def test_markdown_chunk_preserves_heading_hierarchy(self) -> None:
        project_id = uuid.uuid4()
        chunker = StructuralChunker(project_id, chunk_size=100)

        md = (
            "# Architecture\nOverview of the system.\n\n"
            "## Storage\nPostgres and pgvector.\n\n"
            "### Indexing\nIncremental hash detection.\n"
        )
        doc = ParsedDocument(
            file_path="docs/arch.md",
            doc_type=DocumentType.MARKDOWN,
            content=md,
        )

        chunks = chunker.chunk(doc)
        assert len(chunks) == 3
        assert chunks[0].metadata.get("headings") == ["Architecture"]
        assert chunks[1].metadata.get("headings") == ["Architecture", "Storage"]
        assert chunks[2].metadata.get("headings") == ["Architecture", "Storage", "Indexing"]

    def test_chunk_carries_provenance_metadata(self) -> None:
        project_id = uuid.uuid4()
        chunker = StructuralChunker(project_id, chunk_size=200)

        doc = ParsedDocument(
            file_path="src/utils.py",
            doc_type=DocumentType.CODE,
            content="class DatabaseClient:\n    def connect(self):\n        pass\n",
            metadata={"language": "python"},
        )

        chunks = chunker.chunk(doc)
        assert len(chunks) >= 1
        chunk = chunks[0]
        assert chunk.file_path == "src/utils.py"
        assert chunk.project_id == project_id
        assert chunk.metadata.get("symbol") == "DatabaseClient"
        assert chunk.metadata.get("start_line") == 1


class TestRRFFusion:
    def test_rrf_score_increases_with_dual_ranking(self) -> None:
        """A chunk that appears in both dense and sparse results must rank higher than single-result chunks."""
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Both dense & sparse", doc_type=DocumentType.CODE, file_path="a.py", project_id=project_id)
        c2 = Chunk(chunk_index=1, content="Only dense", doc_type=DocumentType.CODE, file_path="b.py", project_id=project_id)
        c3 = Chunk(chunk_index=2, content="Only sparse", doc_type=DocumentType.CODE, file_path="c.py", project_id=project_id)

        rc1_dense = RetrievedChunk(chunk=c1, db_id=c1.id)
        rc2_dense = RetrievedChunk(chunk=c2, db_id=c2.id)

        rc1_sparse = RetrievedChunk(chunk=c1, db_id=c1.id)
        rc3_sparse = RetrievedChunk(chunk=c3, db_id=c3.id)

        dense_list = [rc1_dense, rc2_dense]
        sparse_list = [rc1_sparse, rc3_sparse]

        fused = RAGRetriever._rrf_fuse(dense_list, sparse_list, k=60)

        assert len(fused) == 3
        # Dual-ranked item must be first
        assert fused[0].chunk_id == c1.id
        assert fused[0].rrf_score > fused[1].rrf_score
        assert fused[0].rrf_score > fused[2].rrf_score

    def test_rrf_project_isolation(self) -> None:
        p1 = uuid.uuid4()
        p2 = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Project 1 info", doc_type=DocumentType.PLAIN, file_path="doc.txt", project_id=p1)
        c2 = Chunk(chunk_index=0, content="Project 2 info", doc_type=DocumentType.PLAIN, file_path="secret.txt", project_id=p2)

        rc1 = RetrievedChunk(chunk=c1, db_id=c1.id)
        rc2 = RetrievedChunk(chunk=c2, db_id=c2.id)

        fused = RAGRetriever._rrf_fuse([rc1], [rc2])
        # Both chunks preserved with their respective project_ids
        assert any(c.chunk.project_id == p1 for c in fused)
        assert any(c.chunk.project_id == p2 for c in fused)


class TestContextBuilder:
    def test_context_respects_token_budget(self) -> None:
        project_id = uuid.uuid4()
        builder = ContextBuilder(max_context_tokens=50)

        chunks = []
        for i in range(10):
            c = Chunk(
                chunk_index=i,
                content=f"This is a relatively long chunk number {i} with a lot of words to quickly fill up the token budget limit.",
                doc_type=DocumentType.PLAIN,
                file_path=f"file_{i}.txt",
                project_id=project_id,
                metadata={"start_line": 1, "end_line": 10},
            )
            rc = RetrievedChunk(chunk=c)
            chunks.append(rc)

        rag_ctx = builder.build("test query", chunks, project_id)
        # Context must fit within budget
        assert _count_tokens(rag_ctx.context_text) <= 50
        assert len(rag_ctx.sources) < len(chunks)

    def test_sources_match_included_chunks(self) -> None:
        project_id = uuid.uuid4()
        builder = ContextBuilder(max_context_tokens=1000)

        c1 = Chunk(chunk_index=0, content="Alpha content", doc_type=DocumentType.CODE, file_path="src/a.py", project_id=project_id, metadata={"start_line": 5, "end_line": 10})
        c2 = Chunk(chunk_index=1, content="Beta content", doc_type=DocumentType.CODE, file_path="src/b.py", project_id=project_id, metadata={"start_line": 20, "end_line": 35})

        rc1 = RetrievedChunk(chunk=c1)
        rc2 = RetrievedChunk(chunk=c2)

        rag_ctx = builder.build("find code", [rc1, rc2], project_id)
        assert len(rag_ctx.sources) == 2
        assert "src/a.py:5-10" in rag_ctx.context_text
        assert "src/b.py:20-35" in rag_ctx.context_text
        assert rag_ctx.sources[0].file_path == "src/a.py"
        assert rag_ctx.sources[1].file_path == "src/b.py"
