"""
rag.retriever — Multi-Signal & Provenance-Aware Retriever (RAG V3)

Responsibilities:
  - Parallel dense (pgvector cosine) + sparse (tsvector BM25 / ts_rank) search
  - Natural provenance query understanding:
      - Page intent: "Show information from page 3" -> page_number boost
      - Sheet intent: "Which sheet contains quarterly revenue?" -> sheet_name boost
      - Slide intent: "Find the slide about system architecture" -> slide_number/presentation boost
      - Symbol intent: "Where is parseUser defined?" -> symbol definition boost
  - Multi-signal ranking:
      1. Dense vector semantic similarity (40%)
      2. Sparse keyword rank (30%)
      3. Exact symbol / identifier / phrase match boost (10%)
      4. File path / name match boost (8%)
      5. Structural & provenance intent boost (12%)
  - Deduplicate overlapping or identical chunks before final ranking
  - Enforce strict project isolation on every database query
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from config import settings
from rag.embedder import BaseEmbedder, EmbeddingService
from rag.types import Chunk, DocumentType, RetrievedChunk, SearchMode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_RRF_K = 60

# Weights for multi-signal score synthesis (RAG V3)
_DENSE_WEIGHT = 0.40
_SPARSE_WEIGHT = 0.30
_EXACT_MATCH_WEIGHT = 0.10
_PATH_MATCH_WEIGHT = 0.08
_STRUCTURAL_WEIGHT = 0.12

# Regex patterns for natural provenance query understanding
_PAGE_QUERY_PATTERN = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)
_SLIDE_QUERY_PATTERN = re.compile(r"\bslide\s+(\d+)\b", re.IGNORECASE)
_SHEET_QUERY_PATTERN = re.compile(r"\bsheet\s+['\"]?([a-zA-Z0-9_\-]+)['\"]?", re.IGNORECASE)
_DEF_QUERY_PATTERN = re.compile(r"(?:where is|definition of|defined in|function|class|method)\s+([a-zA-Z0-9_]+)", re.IGNORECASE)


class RAGRetriever:
    """
    Multi-signal and provenance-aware retriever with structural query routing.
    """

    def __init__(
        self,
        db: "AsyncSession",
        model_router: object | None = None,
        embedder: BaseEmbedder | None = None,
        top_k_dense: int = settings.rag_retrieval_top_k_dense,
        top_k_sparse: int = settings.rag_retrieval_top_k_sparse,
        rrf_candidates: int = settings.rag_rrf_candidates,
    ) -> None:
        self._db = db
        self._model_router = model_router
        self._embedder = embedder or EmbeddingService(model_router)
        self._top_k_dense = top_k_dense
        self._top_k_sparse = top_k_sparse
        self._rrf_candidates = rrf_candidates

    async def query(
        self,
        query: str,
        project_id: uuid.UUID,
        mode: SearchMode = SearchMode.HYBRID,
        metadata_filter: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Execute search across a project with specified search mode and structural query parsing.
        """
        if not query.strip():
            return []

        target_limit = limit or self._rrf_candidates
        query_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9_\-]+", query) if len(t) > 1]
        structural_intent = self._extract_structural_intent(query)

        match mode:
            case SearchMode.SEMANTIC:
                chunks = await self._execute_semantic_search(query, project_id, target_limit, metadata_filter)
            case SearchMode.KEYWORD:
                chunks = await self._execute_keyword_search(query, project_id, target_limit, metadata_filter)
            case SearchMode.HYBRID:
                chunks = await self._execute_hybrid_search(query, project_id, metadata_filter)

        # Apply multi-signal boosts (exact match, path match, structural provenance match)
        for rc in chunks:
            self._apply_signal_boosts(rc, query, query_terms, structural_intent)

        # Deduplicate chunks
        deduped = self.deduplicate_chunks(chunks)

        # Sort deterministically
        sorted_chunks = sorted(
            deduped,
            key=lambda rc: (rc.combined_score, rc.rrf_score, str(rc.chunk_id)),
            reverse=True,
        )

        return sorted_chunks[:target_limit]

    # ── Structural Query Intent ────────────────────────────────────────────────

    def _extract_structural_intent(self, query: str) -> dict[str, Any]:
        """Extract explicit intent for pages, slides, sheets, or symbols from query."""
        intent: dict[str, Any] = {}

        # Page intent
        page_match = _PAGE_QUERY_PATTERN.search(query)
        if page_match:
            intent["target_page"] = int(page_match.group(1))

        # Slide intent
        slide_match = _SLIDE_QUERY_PATTERN.search(query)
        if slide_match:
            intent["target_slide"] = int(slide_match.group(1))
        elif "slide" in query.lower() or "presentation" in query.lower():
            intent["prefer_slides"] = True

        # Sheet intent
        sheet_match = _SHEET_QUERY_PATTERN.search(query)
        if sheet_match:
            intent["target_sheet"] = sheet_match.group(1).lower()
        elif "sheet" in query.lower() or "spreadsheet" in query.lower() or "excel" in query.lower():
            intent["prefer_sheets"] = True

        # Symbol definition intent
        def_match = _DEF_QUERY_PATTERN.search(query)
        if def_match:
            intent["target_symbol"] = def_match.group(1)

        return intent

    # ── Multi-Mode Search Execution ────────────────────────────────────────────

    async def _execute_semantic_search(
        self,
        query: str,
        project_id: uuid.UUID,
        limit: int,
        metadata_filter: dict[str, Any] | None,
    ) -> list[RetrievedChunk]:
        try:
            emb = await self._embedder.embed_query(query)
            results = await self._dense_search(emb, project_id, limit)
            if metadata_filter:
                results = [r for r in results if self._matches_filter(r, metadata_filter)]
            for r in results:
                r.combined_score = r.dense_score or 0.0
            return results
        except Exception as e:
            logger.warning("semantic_search_failed", error=str(e))
            return []

    async def _execute_keyword_search(
        self,
        query: str,
        project_id: uuid.UUID,
        limit: int,
        metadata_filter: dict[str, Any] | None,
    ) -> list[RetrievedChunk]:
        results = await self._sparse_search(query, project_id, limit)
        if metadata_filter:
            results = [r for r in results if self._matches_filter(r, metadata_filter)]
        for r in results:
            r.combined_score = r.sparse_score or 0.0
        return results

    async def _execute_hybrid_search(
        self,
        query: str,
        project_id: uuid.UUID,
        metadata_filter: dict[str, Any] | None,
    ) -> list[RetrievedChunk]:
        try:
            query_embedding = await self._embedder.embed_query(query)
        except Exception as e:
            logger.warning("query_embedding_failed_fallback_to_sparse", error=str(e))
            query_embedding = None

        tasks = []
        if query_embedding is not None:
            tasks.append(self._dense_search(query_embedding, project_id, self._top_k_dense))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        tasks.append(self._sparse_search(query, project_id, self._top_k_sparse))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        dense_results: list[RetrievedChunk] = results[0] if isinstance(results[0], list) else []
        sparse_results: list[RetrievedChunk] = results[1] if isinstance(results[1], list) else []

        if metadata_filter:
            dense_results = [r for r in dense_results if self._matches_filter(r, metadata_filter)]
            sparse_results = [r for r in sparse_results if self._matches_filter(r, metadata_filter)]

        return self._rrf_fuse(dense_results, sparse_results, k=_RRF_K)

    # ── Database Searches ──────────────────────────────────────────────────────

    async def _dense_search(
        self, embedding: list[float], project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
        try:
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
                score_val = float(row.score) if row.score is not None else 0.0
                rc = RetrievedChunk(
                    chunk=chunk_obj,
                    db_id=row.id,
                    dense_score=score_val,
                )
                chunks.append(rc)

            return chunks
        except Exception as e:
            logger.error("dense_search_error", error=str(e))
            return []

    async def _sparse_search(
        self, query: str, project_id: uuid.UUID, top_k: int
    ) -> list[RetrievedChunk]:
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
                rank_val = float(row.rank) if row.rank is not None else 0.0
                rc = RetrievedChunk(
                    chunk=chunk_obj,
                    db_id=row.id,
                    sparse_score=rank_val,
                )
                chunks.append(rc)

            return chunks
        except Exception as e:
            logger.error("sparse_search_error", error=str(e))
            return []

    # ── Signal Boosts & Provenance Routing ─────────────────────────────────────

    def _apply_signal_boosts(
        self,
        rc: RetrievedChunk,
        query: str,
        query_terms: list[str],
        structural_intent: dict[str, Any] | None = None,
    ) -> None:
        content_lower = rc.chunk.content.lower()
        file_path_lower = rc.chunk.file_path.lower()
        symbol = rc.chunk.metadata.get("symbol", "")
        headings = rc.chunk.metadata.get("headings", [])
        sheet = rc.sheet_name
        page = rc.page_number
        slide = rc.slide_number
        intent = structural_intent or {}

        # 1. Exact phrase / symbol match boost
        exact_boost = 0.0
        query_stripped = query.strip().lower()
        if symbol and symbol.lower() == query_stripped:
            exact_boost += 1.0
        elif symbol and symbol.lower() in query_terms:
            exact_boost += 0.8
        elif query_stripped in content_lower:
            exact_boost += 0.5
        elif any(f" {t} " in f" {content_lower} " for t in query_terms):
            exact_boost += 0.2

        rc.exact_match_boost = exact_boost

        # 2. File path match boost
        path_boost = 0.0
        if any(t in file_path_lower for t in query_terms):
            path_boost += 0.5
            if any(file_path_lower.endswith(t) or f"/{t}" in file_path_lower for t in query_terms):
                path_boost += 0.5

        rc.path_match_boost = path_boost

        # 3. Structural Intent Boost (RAG V3)
        struct_boost = 0.0

        # Page match
        if "target_page" in intent and page is not None:
            if page == intent["target_page"]:
                struct_boost += 1.0

        # Slide match
        if "target_slide" in intent and slide is not None:
            if slide == intent["target_slide"]:
                struct_boost += 1.0
        elif intent.get("prefer_slides") and (slide is not None or rc.doc_type == DocumentType.DOCUMENT):
            struct_boost += 0.4

        # Sheet match
        if sheet:
            sheet_lower = sheet.lower()
            if "target_sheet" in intent and (sheet_lower == intent["target_sheet"] or intent["target_sheet"] in sheet_lower):
                struct_boost += 1.0
            elif intent.get("prefer_sheets") and (sheet_lower in query.lower() or any(t in sheet_lower for t in query_terms)):
                struct_boost += 1.0
            elif intent.get("prefer_sheets") or rc.doc_type == DocumentType.SPREADSHEET:
                struct_boost += 0.4

        # Symbol match intent
        if "target_symbol" in intent:
            target_sym = intent["target_symbol"].lower()
            if symbol and symbol.lower() == target_sym:
                struct_boost += 1.0
            elif target_sym in content_lower:
                struct_boost += 0.5

        rc.structural_boost = struct_boost

        # 4. Final multi-signal score synthesis
        dense_part = (rc.dense_score or 0.0) * _DENSE_WEIGHT
        sparse_part = min(1.0, (rc.sparse_score or 0.0)) * _SPARSE_WEIGHT
        exact_part = min(1.0, exact_boost) * _EXACT_MATCH_WEIGHT
        path_part = min(1.0, path_boost) * _PATH_MATCH_WEIGHT
        struct_part = min(1.0, struct_boost) * _STRUCTURAL_WEIGHT

        rc.combined_score = dense_part + sparse_part + exact_part + path_part + struct_part

    @staticmethod
    def deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen_ids: set[uuid.UUID] = set()
        seen_spans: set[tuple[str, int | None, int | None]] = set()
        deduped: list[RetrievedChunk] = []

        for rc in chunks:
            cid = rc.chunk_id
            if cid in seen_ids:
                continue

            span_key = (rc.file_path, rc.start_line, rc.end_line)
            if rc.start_line is not None and span_key in seen_spans:
                continue

            seen_ids.add(cid)
            if rc.start_line is not None:
                seen_spans.add(span_key)

            deduped.append(rc)

        return deduped

    @staticmethod
    def _matches_filter(rc: RetrievedChunk, meta_filter: dict[str, Any]) -> bool:
        meta = rc.chunk.metadata
        for k, v in meta_filter.items():
            if k == "file_path":
                if rc.chunk.file_path != v:
                    return False
            elif k == "file_name":
                if rc.file_name != v:
                    return False
            elif k == "doc_type":
                if rc.chunk.doc_type.value != v and str(rc.chunk.doc_type) != v:
                    return False
            elif k == "page_number" or k == "page":
                if rc.page_number != v:
                    return False
            elif k == "sheet_name" or k == "sheet":
                if rc.sheet_name != v:
                    return False
            elif k == "slide_number" or k == "slide":
                if rc.slide_number != v:
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
            else:
                chunks[cid].sparse_rank = rank
                chunks[cid].sparse_score = rc.sparse_score

        for cid, score in scores.items():
            chunks[cid].rrf_score = score

        return sorted(chunks.values(), key=lambda r: r.rrf_score, reverse=True)
