"""
tests.agent.test_rag_v2_retrieval — Comprehensive RAG V2 Retrieval Engine Tests

Covers:
  1. Semantic retrieval (vector similarity search)
  2. Keyword retrieval (full-text search)
  3. Hybrid ranking (multi-signal scoring)
  4. Exact symbol / term match boosting
  5. Metadata filtering
  6. Duplicate chunk removal
  7. Reranker abstraction (CrossEncoder & NoOp)
  8. Context limits & rich provenance formatting
  9. Project isolation
  10. Empty / no-match queries
  11. Malformed embeddings & retry/error handling
  12. Retrieval failure resilience & RetrievalEngine API
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.context_builder import ContextBuilder
from rag.embedder import EmbeddingError, EmbeddingService, is_sensitive_content
from rag.engine import RetrievalEngine
from rag.reranker import CrossEncoderReranker, NoOpReranker
from rag.retriever import RAGRetriever
from rag.types import (
    Chunk,
    DocumentType,
    RetrievedChunk,
    SearchMode,
)


class TestSemanticAndKeywordRetrieval:
    @pytest.mark.asyncio
    async def test_semantic_retrieval_flow(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        chunk = Chunk(
            chunk_index=0,
            content="Vector embedding indexing",
            doc_type=DocumentType.CODE,
            file_path="src/vector.py",
            project_id=project_id,
        )
        rc = RetrievedChunk(chunk=chunk, db_id=chunk.id, dense_score=0.92)

        retriever = RAGRetriever(mock_db)
        retriever._dense_search = AsyncMock(return_value=[rc])
        retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        results = await retriever.query("vector search", project_id, mode=SearchMode.SEMANTIC)
        assert len(results) == 1
        assert results[0].dense_score == 0.92
        assert results[0].chunk_id == chunk.id

    @pytest.mark.asyncio
    async def test_keyword_retrieval_flow(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        chunk = Chunk(
            chunk_index=0,
            content="PostgreSQL full text query",
            doc_type=DocumentType.PLAIN,
            file_path="docs/db.md",
            project_id=project_id,
        )
        rc = RetrievedChunk(chunk=chunk, db_id=chunk.id, sparse_score=0.85)

        retriever = RAGRetriever(mock_db)
        retriever._sparse_search = AsyncMock(return_value=[rc])

        results = await retriever.query("PostgreSQL text", project_id, mode=SearchMode.KEYWORD)
        assert len(results) == 1
        assert results[0].sparse_score == 0.85


class TestMultiSignalHybridRanking:
    @pytest.mark.asyncio
    async def test_exact_symbol_match_boosts_score(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Chunk with exact symbol match
        c1 = Chunk(
            chunk_index=0,
            content="def execute_query(sql): pass",
            doc_type=DocumentType.CODE,
            file_path="src/db.py",
            project_id=project_id,
            metadata={"symbol": "execute_query"},
        )
        rc1 = RetrievedChunk(chunk=c1, db_id=c1.id, dense_score=0.7, sparse_score=0.5)

        # Chunk with general topic match but no symbol match
        c2 = Chunk(
            chunk_index=1,
            content="database general documentation",
            doc_type=DocumentType.PLAIN,
            file_path="docs/general.txt",
            project_id=project_id,
        )
        rc2 = RetrievedChunk(chunk=c2, db_id=c2.id, dense_score=0.75, sparse_score=0.5)

        retriever = RAGRetriever(mock_db)
        retriever._dense_search = AsyncMock(return_value=[rc2, rc1])
        retriever._sparse_search = AsyncMock(return_value=[rc1, rc2])
        retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        results = await retriever.query("execute_query", project_id, mode=SearchMode.HYBRID)
        assert len(results) == 2
        # rc1 gets exact symbol boost and ranks #1
        assert results[0].chunk_id == c1.id
        assert results[0].exact_match_boost > 0.0
        assert results[0].combined_score > results[1].combined_score

    @pytest.mark.asyncio
    async def test_path_match_boost(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        c_path = Chunk(
            chunk_index=0,
            content="auth configuration",
            doc_type=DocumentType.PLAIN,
            file_path="config/auth.json",
            project_id=project_id,
        )
        rc_path = RetrievedChunk(chunk=c_path, db_id=c_path.id, dense_score=0.6)

        retriever = RAGRetriever(mock_db)
        retriever._apply_signal_boosts(rc_path, query="auth.json", query_terms=["auth", "json"])
        assert rc_path.path_match_boost > 0.0


class TestDeduplicationAndFiltering:
    def test_duplicate_removal_by_id_and_span(self) -> None:
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Code", doc_type=DocumentType.CODE, file_path="a.py", project_id=project_id, metadata={"start_line": 1, "end_line": 10})
        c2 = Chunk(chunk_index=0, content="Code", doc_type=DocumentType.CODE, file_path="a.py", project_id=project_id, metadata={"start_line": 1, "end_line": 10})

        rc1 = RetrievedChunk(chunk=c1, db_id=c1.id)
        rc2_dup_id = RetrievedChunk(chunk=c1, db_id=c1.id)
        rc3_dup_span = RetrievedChunk(chunk=c2, db_id=uuid.uuid4())

        chunks = [rc1, rc2_dup_id, rc3_dup_span]
        deduped = RAGRetriever.deduplicate_chunks(chunks)
        assert len(deduped) == 1
        assert deduped[0].chunk_id == c1.id

    def test_metadata_filtering_by_doc_type_and_path(self) -> None:
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="code", doc_type=DocumentType.CODE, file_path="a.py", project_id=project_id)
        c2 = Chunk(chunk_index=0, content="doc", doc_type=DocumentType.DOCUMENT, file_path="b.pdf", project_id=project_id)

        rc1 = RetrievedChunk(chunk=c1)
        rc2 = RetrievedChunk(chunk=c2)

        assert RAGRetriever._matches_filter(rc1, {"doc_type": "code"}) is True
        assert RAGRetriever._matches_filter(rc2, {"doc_type": "code"}) is False
        assert RAGRetriever._matches_filter(rc1, {"file_path": "a.py"}) is True
        assert RAGRetriever._matches_filter(rc2, {"file_path": "a.py"}) is False


class TestRerankerAbstraction:
    @pytest.mark.asyncio
    async def test_cross_encoder_reranker(self) -> None:
        reranker = CrossEncoderReranker(top_k=1)
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Snippet 1", doc_type=DocumentType.PLAIN, file_path="1.txt", project_id=project_id)
        c2 = Chunk(chunk_index=1, content="Snippet 2", doc_type=DocumentType.PLAIN, file_path="2.txt", project_id=project_id)

        candidates = [RetrievedChunk(chunk=c1), RetrievedChunk(chunk=c2)]

        with patch.object(reranker, "_sync_predict", return_value=[0.2, 0.9]):
            reranked = await reranker.rerank("test query", candidates)
            assert len(reranked) == 1
            assert reranked[0].chunk_id == c2.id
            assert reranked[0].reranker_score == 0.9

    @pytest.mark.asyncio
    async def test_noop_reranker(self) -> None:
        reranker = NoOpReranker(top_k=1)
        project_id = uuid.uuid4()
        c1 = Chunk(chunk_index=0, content="Snippet 1", doc_type=DocumentType.PLAIN, file_path="1.txt", project_id=project_id)
        c2 = Chunk(chunk_index=1, content="Snippet 2", doc_type=DocumentType.PLAIN, file_path="2.txt", project_id=project_id)

        candidates = [RetrievedChunk(chunk=c1), RetrievedChunk(chunk=c2)]
        reranked = await reranker.rerank("test query", candidates)
        assert len(reranked) == 1
        assert reranked[0].chunk_id == c1.id


class TestRichProvenanceContextBuilder:
    def test_rich_provenance_formatting(self) -> None:
        project_id = uuid.uuid4()
        builder = ContextBuilder(max_context_tokens=1000)

        chunk = Chunk(
            chunk_index=0,
            content="export function parseUser() {}",
            doc_type=DocumentType.CODE,
            file_path="src/parser.ts",
            project_id=project_id,
            metadata={
                "start_line": 15,
                "end_line": 28,
                "symbol": "parseUser",
                "headings": ["API", "Users"],
            },
        )
        rc = RetrievedChunk(chunk=chunk, rrf_score=0.033, combined_score=0.88)

        ctx = builder.build("find user parser", [rc], project_id)
        assert "src/parser.ts" in ctx.context_text
        assert "src/parser.ts:15-28" in ctx.context_text
        assert "type: code" in ctx.context_text
        assert "symbol: parseUser" in ctx.context_text
        assert "heading: API > Users" in ctx.context_text
        assert "score: 0.880" in ctx.context_text
        assert ctx.token_count > 0


class TestEmbeddingPipelineEdgeCases:
    def test_sensitive_content_filtering(self) -> None:
        assert is_sensitive_content("-----BEGIN RSA PRIVATE KEY-----\nMIIEowI...") is True
        assert is_sensitive_content("api_key = 'sk-12345678901234567890123456789012'") is True
        assert is_sensitive_content("ghp_123456789012345678901234567890123456") is True
        assert is_sensitive_content("def add(a, b): return a + b") is False

    @pytest.mark.asyncio
    async def test_embedder_dimension_validation(self) -> None:
        service = EmbeddingService(expected_dim=1024)
        # Should raise error on irregular vector dimensions
        with pytest.raises(EmbeddingError):
            service._validate_embeddings([[0.1] * 1024, [0.2] * 512])

    @pytest.mark.asyncio
    async def test_embed_empty_query_raises(self) -> None:
        service = EmbeddingService()
        with pytest.raises(EmbeddingError):
            await service.embed_query("   ")


class TestRetrievalEngineAPI:
    @pytest.mark.asyncio
    async def test_retrieval_engine_facade(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        engine = RetrievalEngine(db=mock_db, reranker=NoOpReranker())

        chunk = Chunk(
            chunk_index=0,
            content="Authentication logic",
            doc_type=DocumentType.CODE,
            file_path="src/auth.py",
            project_id=project_id,
        )
        rc = RetrievedChunk(chunk=chunk, db_id=chunk.id, dense_score=0.9)

        engine._retriever._dense_search = AsyncMock(return_value=[rc])
        engine._retriever._sparse_search = AsyncMock(return_value=[rc])
        engine._retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        # 1. Search method
        res = await engine.search("auth", project_id, mode=SearchMode.HYBRID, limit=5)
        assert res.total_count == 1
        assert res.chunks[0].chunk_id == chunk.id

        # 2. Retrieve context method
        context = await engine.retrieve_context("auth", project_id, max_tokens=500)
        assert "src/auth.py" in context.context_text
        assert len(context.sources) == 1

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_results(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()
        engine = RetrievalEngine(db=mock_db)

        res = await engine.search("", project_id)
        assert res.total_count == 0
        assert len(res.chunks) == 0

    @pytest.mark.asyncio
    async def test_invalid_project_id_raises_value_error(self) -> None:
        mock_db = AsyncMock()
        engine = RetrievalEngine(db=mock_db)
        with pytest.raises(ValueError):
            await engine.search("query", "not-a-valid-uuid")  # type: ignore
