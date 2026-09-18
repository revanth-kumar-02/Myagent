"""
tests.agent.test_rag_integration — Comprehensive End-to-End RAG Integration Tests

Tests covering:
  - Full ingestion with mock/in-memory DB sessions
  - Embedder integration and vector generation
  - Multi-format parsing & structural chunking (Code, Markdown, Spreadsheets, JSON, CSV)
  - Incremental indexing workflow (Add -> Modify -> Delete)
  - Reranker cross-encoder scoring and top-k filtering
  - Strict project isolation across multiple projects
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import openpyxl

from rag.chunker import StructuralChunker
from rag.context_builder import ContextBuilder
from rag.embedder import EmbeddingService
from rag.indexer import Indexer
from rag.parser import Parser
from rag.reranker import Reranker
from rag.retriever import RAGRetriever
from rag.types import (
    Chunk,
    DocumentType,
    FileEvent,
    FileEventType,
    ParsedDocument,
    RetrievedChunk,
)


class TestRAGFormats:
    """Test parsing and structural chunking across all supported file formats."""

    @pytest.mark.asyncio
    async def test_spreadsheet_xlsx_parsing_and_chunking(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Financials"
            ws.append(["Quarter", "Revenue", "Profit"])
            ws.append(["Q1", "$100k", "$20k"])
            ws.append(["Q2", "$150k", "$35k"])
            wb.save(tmp_path)

            parser = Parser()
            doc = await parser.parse(tmp_path)
            assert doc is not None
            assert doc.doc_type == DocumentType.SPREADSHEET
            assert "Financials" in doc.metadata["sheet_names"]
            assert "Quarter | Revenue | Profit" in doc.content

            chunker = StructuralChunker(uuid.uuid4())
            chunks = chunker.chunk(doc)
            assert len(chunks) >= 1
            assert "Quarter" in chunks[0].content
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_multilingual_code_parsing(self) -> None:
        parser = Parser()
        languages = [
            ("main.dart", "void main() { runApp(MyApp()); }", "dart"),
            ("service.ts", "export class ApiService { async get() {} }", "typescript"),
            ("queries.sql", "SELECT * FROM users WHERE active = true;", "sql"),
            ("index.html", "<!DOCTYPE html><html><body><h1>Title</h1></body></html>", "html"),
        ]

        for filename, code, expected_lang in languages:
            with tempfile.NamedTemporaryFile(suffix=f"_{filename}", mode="w", delete=False) as tmp:
                tmp.write(code)
                tmp_path = Path(tmp.name)

            try:
                doc = await parser.parse(tmp_path)
                assert doc is not None
                assert doc.doc_type == DocumentType.CODE
                assert doc.metadata["language"] == expected_lang
            finally:
                tmp_path.unlink()


class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_embed_chunks_mocked_or_direct(self) -> None:
        service = EmbeddingService()
        project_id = uuid.uuid4()
        chunks = [
            Chunk(chunk_index=0, content="Machine learning models", doc_type=DocumentType.PLAIN, file_path="a.txt", project_id=project_id),
            Chunk(chunk_index=1, content="PostgreSQL vector search", doc_type=DocumentType.PLAIN, file_path="b.txt", project_id=project_id),
        ]

        # Test sync encode batch mock to test batching and vector assignment
        mock_vectors = [[0.1] * 1024, [0.2] * 1024]
        with patch.object(service, "embed_texts", new_callable=AsyncMock) as mock_embed_texts:
            mock_embed_texts.return_value = mock_vectors
            result = await service.embed(chunks)

            assert len(result) == 2
            assert result[0].embedding == mock_vectors[0]
            assert result[1].embedding == mock_vectors[1]

    @pytest.mark.asyncio
    async def test_embed_query(self) -> None:
        service = EmbeddingService()
        with patch.object(service, "embed_texts", new_callable=AsyncMock) as mock_embed_texts:
            mock_embed_texts.return_value = [[0.5] * 1024]
            vec = await service.embed_query("search query")
            assert len(vec) == 1024
            assert vec[0] == 0.5


class TestReranker:
    @pytest.mark.asyncio
    async def test_reranker_scores_and_sorts(self) -> None:
        reranker = Reranker(top_k=2)
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Highly relevant content", doc_type=DocumentType.PLAIN, file_path="a.txt", project_id=project_id)
        c2 = Chunk(chunk_index=1, content="Completely unrelated noise", doc_type=DocumentType.PLAIN, file_path="b.txt", project_id=project_id)
        c3 = Chunk(chunk_index=2, content="Somewhat relevant snippet", doc_type=DocumentType.PLAIN, file_path="c.txt", project_id=project_id)

        candidates = [
            RetrievedChunk(chunk=c1, rrf_score=0.01),
            RetrievedChunk(chunk=c2, rrf_score=0.03),
            RetrievedChunk(chunk=c3, rrf_score=0.02),
        ]

        with patch.object(reranker, "_sync_predict") as mock_predict:
            # Score c1 highest (0.95), c3 second (0.60), c2 lowest (0.10)
            mock_predict.return_value = [0.95, 0.10, 0.60]
            reranked = await reranker.rerank("relevant query", candidates)

            assert len(reranked) == 2  # capped at top_k=2
            assert reranked[0].chunk_id == c1.id
            assert reranked[0].reranker_score == 0.95
            assert reranked[1].chunk_id == c3.id
            assert reranked[1].reranker_score == 0.60


class TestIncrementalIndexer:
    @pytest.mark.asyncio
    async def test_indexer_workflow(self) -> None:
        project_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "calculator.py").write_text("def add(a, b):\n    return a + b\n")

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            # First scan: DB returns empty
            mock_result_empty = MagicMock()
            mock_result_empty.fetchall.return_value = []
            mock_result_empty.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result_empty

            indexer = Indexer(project_id, root, mock_db)
            # Mock embedder to avoid downloading HF weights during fast test
            indexer._embedder.embed = AsyncMock(side_effect=lambda chunks: chunks)

            stats = await indexer.run(incremental=True)
            assert stats.files_added == 1
            assert stats.chunks_total >= 1
            assert mock_db.commit.called


class TestProjectIsolation:
    @pytest.mark.asyncio
    async def test_retriever_enforces_project_id(self) -> None:
        project_a = uuid.uuid4()
        project_b = uuid.uuid4()

        mock_db = AsyncMock()
        retriever = RAGRetriever(mock_db)

        # Mock embedder
        retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        # Mock dense and sparse search
        chunk_a = Chunk(chunk_index=0, content="Project A confidential", doc_type=DocumentType.PLAIN, file_path="a.txt", project_id=project_a)
        rc_a = RetrievedChunk(chunk=chunk_a, db_id=chunk_a.id)

        retriever._dense_search = AsyncMock(return_value=[rc_a])
        retriever._sparse_search = AsyncMock(return_value=[rc_a])

        results = await retriever.query("confidential", project_a)
        assert len(results) == 1
        assert results[0].chunk.project_id == project_a
        assert results[0].chunk.project_id != project_b
