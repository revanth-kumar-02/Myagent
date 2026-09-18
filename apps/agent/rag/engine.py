"""
rag.engine — High-Level Retrieval Engine API (RAG V2)

Responsibilities:
  - Unified public entry point for all retrieval operations
  - Project-scoped search with SearchMode (HYBRID, SEMANTIC, KEYWORD)
  - Seamless retrieval → reranking → context assembly pipeline
  - Independent dependency injection for embedder, retriever, reranker, and context builder
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from rag.context_builder import ContextBuilder
from rag.embedder import BaseEmbedder, EmbeddingService
from rag.reranker import BaseReranker, CrossEncoderReranker
from rag.retriever import RAGRetriever
from rag.types import RAGContext, RetrievalResult, RetrievedChunk, SearchMode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class RetrievalEngine:
    """
    Public API Facade for Kora RAG V2 Retrieval Engine.
    """

    def __init__(
        self,
        db: "AsyncSession",
        model_router: object | None = None,
        embedder: BaseEmbedder | None = None,
        retriever: RAGRetriever | None = None,
        reranker: BaseReranker | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self._db = db
        self._embedder = embedder or EmbeddingService(model_router)
        self._retriever = retriever or RAGRetriever(db, model_router, embedder=self._embedder)
        self._reranker = reranker or CrossEncoderReranker(model_router)
        self._context_builder = context_builder or ContextBuilder()

    async def search(
        self,
        query: str,
        project_id: uuid.UUID,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        enable_reranking: bool = True,
    ) -> RetrievalResult:
        """
        Execute project-scoped search with specified SearchMode and optional reranking.
        """
        start = time.monotonic()
        if not isinstance(project_id, uuid.UUID):
            try:
                project_id = uuid.UUID(str(project_id))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid project_id: {project_id}") from exc

        candidates = await self._retriever.query(
            query=query,
            project_id=project_id,
            mode=mode,
            metadata_filter=metadata_filter,
            limit=limit * 2 if enable_reranking else limit,
        )

        if enable_reranking and candidates:
            final_chunks = await self._reranker.rerank(query, candidates, top_k=limit)
        else:
            final_chunks = candidates[:limit]

        latency = int((time.monotonic() - start) * 1000)
        return RetrievalResult(
            chunks=final_chunks,
            query=query,
            project_id=project_id,
            mode=mode,
            total_count=len(final_chunks),
            latency_ms=latency,
        )

    async def hybrid_search(
        self,
        query: str,
        project_id: uuid.UUID,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Convenience method for hybrid search."""
        res = await self.search(
            query=query,
            project_id=project_id,
            mode=SearchMode.HYBRID,
            limit=limit,
            metadata_filter=metadata_filter,
        )
        return res.chunks

    async def semantic_search(
        self,
        query: str,
        project_id: uuid.UUID,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Convenience method for dense vector semantic search."""
        res = await self.search(
            query=query,
            project_id=project_id,
            mode=SearchMode.SEMANTIC,
            limit=limit,
            metadata_filter=metadata_filter,
        )
        return res.chunks

    async def keyword_search(
        self,
        query: str,
        project_id: uuid.UUID,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Convenience method for sparse keyword / BM25 search."""
        res = await self.search(
            query=query,
            project_id=project_id,
            mode=SearchMode.KEYWORD,
            limit=limit,
            metadata_filter=metadata_filter,
        )
        return res.chunks

    async def retrieve_context(
        self,
        query: str,
        project_id: uuid.UUID,
        max_tokens: int = 4096,
        metadata_filter: dict[str, Any] | None = None,
        search_limit: int = 20,
    ) -> RAGContext:
        """
        Execute full pipeline: Hybrid search → Cross-encoder rerank → Bounded context assembly.
        """
        res = await self.search(
            query=query,
            project_id=project_id,
            mode=SearchMode.HYBRID,
            limit=search_limit,
            metadata_filter=metadata_filter,
            enable_reranking=True,
        )
        return self._context_builder.build(
            query=query,
            chunks=res.chunks,
            project_id=project_id,
            max_tokens=max_tokens,
        )
