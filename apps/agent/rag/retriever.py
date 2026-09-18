"""
rag.retriever — Hybrid Retriever

Responsibilities:
  - Execute parallel dense (pgvector cosine) + sparse (tsvector BM25) searches
  - Fuse results with Reciprocal Rank Fusion (RRF)
  - Enforce project isolation: all queries filter on project_id
  - Support metadata post-filtering (file_type, date range, etc.)
  - Return a ranked list of RetrievedChunks for the Reranker

This component ONLY reads from the database. It never writes.

Algorithm:
  1. Embed query using EmbeddingService
  2. Run dense search: SELECT ... ORDER BY embedding <=> $1 LIMIT top_k
  3. Run sparse search: SELECT ... WHERE tsv @@ plainto_tsquery($1) ORDER BY rank LIMIT top_k
  4. Merge with RRF: score(i) = Σ 1/(k + rank_i), k=60
  5. Return top rrf_candidates sorted by RRF score
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from config import settings
from rag.types import RAGContext, RetrievedChunk

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_RRF_K = 60  # standard RRF constant


class RAGRetriever:
    """
    Hybrid retriever: dense vector search + sparse full-text search, fused via RRF.
    Every query is strictly project-scoped.
    """

    def __init__(
        self,
        db: "AsyncSession",
        model_router: object,
        top_k_dense: int = settings.rag_retrieval_top_k_dense,
        top_k_sparse: int = settings.rag_retrieval_top_k_sparse,
        rrf_candidates: int = settings.rag_rrf_candidates,
    ) -> None:
        self._db = db
        self._model_router = model_router
        self._top_k_dense = top_k_dense
        self._top_k_sparse = top_k_sparse
        self._rrf_candidates = rrf_candidates

    async def query(
        self,
        query: str,
        project_id: uuid.UUID,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """
        Execute hybrid retrieval for a query within a project.

        Returns RetrievedChunks sorted by RRF score (highest first),
        capped at rrf_candidates. The Reranker further reduces this list.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    # ── Private helpers (stubs) ────────────────────────────────────────────────

    async def _dense_search(
        self, embedding: list[float], project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
        """pgvector cosine similarity search."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def _sparse_search(
        self, query: str, project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
        """PostgreSQL tsvector full-text search."""
        raise NotImplementedError  # TODO: implement in feature phase

    @staticmethod
    def _rrf_fuse(
        dense: list[RetrievedChunk],
        sparse: list[RetrievedChunk],
        k: int = _RRF_K,
    ) -> list[RetrievedChunk]:
        """
        Reciprocal Rank Fusion.

        score(chunk) = 1/(k + dense_rank) + 1/(k + sparse_rank)
        Chunks that only appear in one list get contribution only from that list.
        """
        scores: dict[uuid.UUID, float] = {}
        chunks: dict[uuid.UUID, RetrievedChunk] = {}

        for rank, rc in enumerate(dense, start=1):
            cid = rc.db_id or rc.chunk.id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            rc.dense_rank = rank
            chunks[cid] = rc

        for rank, rc in enumerate(sparse, start=1):
            cid = rc.db_id or rc.chunk.id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            rc.sparse_rank = rank
            if cid not in chunks:
                chunks[cid] = rc

        for cid, score in scores.items():
            chunks[cid].rrf_score = score

        return sorted(chunks.values(), key=lambda r: r.rrf_score, reverse=True)
