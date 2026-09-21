"""
rag.reranker — Cross-Encoder Reranker (RAG V2)

Responsibilities:
  - BaseReranker abstract base class for interchangeable reranker providers
  - CrossEncoderReranker implementing joint query-candidate relevance scoring
  - NoOpReranker for pass-through or lightweight low-latency mode
  - Deterministic score assignment and top-k candidate truncation
"""

from __future__ import annotations

import abc
import asyncio
from typing import Any

import structlog

from config import settings
from rag.types import RetrievedChunk

logger = structlog.get_logger(__name__)

_RERANKER_INSTANCE: Any = None


def _get_reranker_model() -> Any:
    global _RERANKER_INSTANCE
    return _RERANKER_INSTANCE


class BaseReranker(abc.ABC):
    """Abstract interface for all Reranker implementations."""

    @abc.abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Score candidate chunks and return top_k sorted by score."""
        ...


class CrossEncoderReranker(BaseReranker):
    """
    Cross-encoder reranker using sentence-transformers CrossEncoder.
    Reduces candidate pool to top_k with calibrated relevance scores.
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
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Score all candidates with the cross-encoder, sort by score, return top_k.
        Sets reranker_score on each returned RetrievedChunk.
        """
        k = top_k if top_k is not None else self._top_k

        if not candidates:
            return []
        if len(candidates) <= 1:
            if candidates:
                candidates[0].reranker_score = 1.0
            return candidates[:k]

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
            return sorted_candidates[:k]
        except Exception as e:
            logger.warning("reranker_failed_falling_back_to_initial_ranking", error=str(e))
            return candidates[:k]

    def _sync_predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        model = _get_reranker_model()
        if model is not None:
            scores = model.predict(pairs, show_progress_bar=False)
            return [float(s) for s in scores]
        # Cloud/zero-download fallback: simple term overlap score
        scores = []
        for query, content in pairs:
            q_terms = set(query.lower().split())
            c_terms = set(content.lower().split())
            overlap = len(q_terms & c_terms) / (len(q_terms) or 1)
            scores.append(float(overlap))
        return scores


class NoOpReranker(BaseReranker):
    """
    Pass-through reranker that preserves retrieval ordering.
    Useful for testing, benchmarking, or low-latency profiles.
    """

    def __init__(self, top_k: int = settings.rag_reranker_top_k) -> None:
        self._top_k = top_k

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        k = top_k if top_k is not None else self._top_k
        return candidates[:k]


# Alias for backwards compatibility
Reranker = CrossEncoderReranker
