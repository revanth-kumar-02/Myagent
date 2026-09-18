"""
rag.reranker — Cross-Encoder Reranker

Responsibilities:
  - Accept a list of RetrievedChunks (post-RRF fusion)
  - Re-score each chunk against the original query using a cross-encoder model
  - Return top-k chunks sorted by reranker score (highest first)
  - Model is resolved from registry via capability tag (not hardcoded here)

The cross-encoder evaluates (query, chunk_content) pairs jointly,
producing a relevance score that is significantly more accurate than
the cosine / BM25 scores from first-stage retrieval.

Implementation note: sentence-transformers CrossEncoder is used via the
HuggingFace provider. The model is configured in registry.yaml.
"""

from __future__ import annotations

import structlog

from config import settings
from rag.types import RetrievedChunk

logger = structlog.get_logger(__name__)


class Reranker:
    """
    Cross-encoder reranker.
    Reduces the candidate pool from rrf_candidates → reranker_top_k.
    """

    def __init__(
        self,
        model_router: object,
        top_k: int = settings.rag_reranker_top_k,
    ) -> None:
        self._model_router = model_router
        self._top_k = top_k

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """
        Score all candidates with the cross-encoder, sort by score, return top_k.
        Sets reranker_score on each returned RetrievedChunk.
        """
        if not candidates:
            return []
        if len(candidates) <= self._top_k:
            return candidates

        raise NotImplementedError  # TODO: implement in feature phase
