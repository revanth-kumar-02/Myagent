"""
rag.reranker — Cross-Encoder Reranker

Responsibilities:
  - Accept a list of RetrievedChunks (post-RRF fusion)
  - Re-score each chunk against the original query using a cross-encoder model
  - Return top-k chunks sorted by reranker score (highest first)
  - Model is resolved lazily via sentence-transformers CrossEncoder or model router

The cross-encoder evaluates (query, chunk_content) pairs jointly,
producing a relevance score that is significantly more accurate than
the cosine / BM25 scores from first-stage retrieval.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from config import settings
from rag.types import RetrievedChunk

logger = structlog.get_logger(__name__)

_RERANKER_INSTANCE: Any = None


def _get_reranker_model() -> Any:
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        try:
            from sentence_transformers import CrossEncoder

            model_name = getattr(
                settings, "rag_reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            logger.info("loading_reranker_model", model_name=model_name)
            _RERANKER_INSTANCE = CrossEncoder(model_name)
        except Exception as e:
            logger.error("failed_to_load_reranker_model", error=str(e))
            raise RuntimeError(f"Failed to load reranker model: {e}") from e
    return _RERANKER_INSTANCE


class Reranker:
    """
    Cross-encoder reranker.
    Reduces the candidate pool from rrf_candidates → reranker_top_k.
    """

    def __init__(
        self,
        model_router: object | None = None,
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
        if len(candidates) <= 1:
            if candidates:
                candidates[0].reranker_score = 1.0
            return candidates

        try:
            pairs = [(query, rc.chunk.content) for rc in candidates]
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(None, self._sync_predict, pairs)

            for rc, score in zip(candidates, scores):
                rc.reranker_score = float(score)

            sorted_candidates = sorted(
                candidates,
                key=lambda rc: rc.reranker_score if rc.reranker_score is not None else -1e9,
                reverse=True,
            )
            return sorted_candidates[: self._top_k]
        except Exception as e:
            logger.warning("reranker_failed_falling_back_to_rrf", error=str(e))
            return candidates[: self._top_k]

    def _sync_predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        model = _get_reranker_model()
        scores = model.predict(pairs, show_progress_bar=False)
        return [float(s) for s in scores]
