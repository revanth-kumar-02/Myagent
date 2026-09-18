"""
rag.retriever — Hybrid Retriever

Responsibilities:
  - Execute parallel dense (pgvector cosine) + sparse (tsvector BM25/ts_rank) searches
  - Fuse results with Reciprocal Rank Fusion (RRF)
  - Enforce project isolation: all queries filter on project_id
  - Support metadata post-filtering (file_type, date range, etc.)
  - Return a ranked list of RetrievedChunks for the Reranker

This component ONLY reads from the database. It never writes.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from config import settings
from rag.embedder import EmbeddingService
from rag.types import Chunk, DocumentType, RetrievedChunk

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
        model_router: object | None = None,
        top_k_dense: int = settings.rag_retrieval_top_k_dense,
        top_k_sparse: int = settings.rag_retrieval_top_k_sparse,
        rrf_candidates: int = settings.rag_rrf_candidates,
    ) -> None:
        self._db = db
        self._model_router = model_router
        self._top_k_dense = top_k_dense
        self._top_k_sparse = top_k_sparse
        self._rrf_candidates = rrf_candidates
        self._embedder = EmbeddingService(model_router)

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
        if not query.strip():
            return []

        # 1. Embed query vector
        try:
            query_embedding = await self._embedder.embed_query(query)
        except Exception as e:
            logger.warning("query_embedding_failed_fallback_to_sparse", error=str(e))
            query_embedding = None

        # 2. Parallel dense + sparse searches
        tasks = []
        if query_embedding is not None:
            tasks.append(self._dense_search(query_embedding, project_id, self._top_k_dense))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        tasks.append(self._sparse_search(query, project_id, self._top_k_sparse))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        dense_results: list[RetrievedChunk] = results[0] if isinstance(results[0], list) else []
        sparse_results: list[RetrievedChunk] = results[1] if isinstance(results[1], list) else []

        # 3. Apply metadata filtering if specified
        if metadata_filter:
            dense_results = [r for r in dense_results if self._matches_filter(r, metadata_filter)]
            sparse_results = [r for r in sparse_results if self._matches_filter(r, metadata_filter)]

        # 4. Fuse with RRF
        fused = self._rrf_fuse(dense_results, sparse_results, k=_RRF_K)

        # 5. Return top candidates
        return fused[: self._rrf_candidates]

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _dense_search(
        self, embedding: list[float], project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
        """pgvector cosine distance similarity search."""
        try:
            # Format vector literal for pgvector
            emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
            sql = text(
                """
                SELECT c.id, c.project_id, c.file_id, c.chunk_index, c.content,
                       c.metadata, f.file_path,
                       (1 - (c.embedding <=> CAST(:emb AS vector))) AS score
                FROM chunks c
                JOIN indexed_files f ON c.file_id = f.id
                WHERE c.project_id = :project_id
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:emb AS vector)
                LIMIT :limit
                """
            )
            result = await self._db.execute(sql, {"emb": emb_str, "project_id": str(project_id), "limit": top_k})
            rows = result.fetchall()

            chunks: list[RetrievedChunk] = []
            for row in rows:
                meta = row.metadata if isinstance(row.metadata, dict) else {}
                doc_type_val = meta.get("doc_type", "plain")
                try:
                    doc_type = DocumentType(doc_type_val)
                except Exception:
                    doc_type = DocumentType.PLAIN

                chunk_obj = Chunk(
                    id=row.id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    doc_type=doc_type,
                    file_path=row.file_path,
                    project_id=row.project_id,
                    metadata=meta,
                )
                rc = RetrievedChunk(
                    chunk=chunk_obj,
                    db_id=row.id,
                )
                chunks.append(rc)

            return chunks
        except Exception as e:
            logger.error("dense_search_error", error=str(e))
            return []

    async def _sparse_search(
        self, query: str, project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
        """PostgreSQL tsvector full-text search."""
        try:
            sql = text(
                """
                SELECT c.id, c.project_id, c.file_id, c.chunk_index, c.content,
                       c.metadata, f.file_path,
                       ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) AS rank
                FROM chunks c
                JOIN indexed_files f ON c.file_id = f.id
                WHERE c.project_id = :project_id
                  AND c.tsv @@ plainto_tsquery('english', :q)
                ORDER BY rank DESC
                LIMIT :limit
                """
            )
            result = await self._db.execute(sql, {"q": query, "project_id": str(project_id), "limit": top_k})
            rows = result.fetchall()

            chunks: list[RetrievedChunk] = []
            for row in rows:
                meta = row.metadata if isinstance(row.metadata, dict) else {}
                doc_type_val = meta.get("doc_type", "plain")
                try:
                    doc_type = DocumentType(doc_type_val)
                except Exception:
                    doc_type = DocumentType.PLAIN

                chunk_obj = Chunk(
                    id=row.id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    doc_type=doc_type,
                    file_path=row.file_path,
                    project_id=row.project_id,
                    metadata=meta,
                )
                rc = RetrievedChunk(
                    chunk=chunk_obj,
                    db_id=row.id,
                )
                chunks.append(rc)

            return chunks
        except Exception as e:
            logger.error("sparse_search_error", error=str(e))
            return []

    @staticmethod
    def _matches_filter(rc: RetrievedChunk, meta_filter: dict[str, Any]) -> bool:
        meta = rc.chunk.metadata
        for k, v in meta_filter.items():
            if k == "file_path":
                if rc.chunk.file_path != v:
                    return False
            elif k == "doc_type":
                if rc.chunk.doc_type.value != v and str(rc.chunk.doc_type) != v:
                    return False
            elif meta.get(k) != v:
                return False
        return True

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
