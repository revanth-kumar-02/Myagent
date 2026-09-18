"""
rag.embedder — Embedding Service

Responsibilities:
  - Accept a list of Chunks or text strings
  - Batch-embed them using the embedding model (SentenceTransformer / BGE-M3 / MiniLM)
  - Attach the resulting vectors to each Chunk
  - Return the annotated Chunks (embedding field populated)
  - Support direct query embedding for retriever

Embedding model is loaded lazily as a process-level singleton.
Model ID is configurable via settings.rag_embed_model.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from config import settings
from rag.types import Chunk

logger = structlog.get_logger(__name__)

_MODEL_INSTANCE: Any = None
_MODEL_LOCK = asyncio.Lock()


def _get_embedding_model() -> Any:
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        try:
            from sentence_transformers import SentenceTransformer

            model_name = getattr(settings, "rag_embed_model", "BAAI/bge-m3")
            logger.info("loading_embedding_model", model_name=model_name)
            _MODEL_INSTANCE = SentenceTransformer(model_name)
        except Exception as e:
            logger.error("failed_to_load_embedding_model", error=str(e))
            raise EmbeddingError(f"Failed to load embedding model: {e}") from e
    return _MODEL_INSTANCE


class EmbeddingService:
    """
    Batch-embeds Chunks and query strings using the configured embedding model.
    """

    def __init__(self, model_router: object | None = None) -> None:
        self._model_router = model_router
        self._batch_size = getattr(settings, "rag_embedding_batch_size", 32)

    async def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Embed a list of Chunks in batches.

        Modifies chunks in-place (sets chunk.embedding) and returns the list.
        Raises EmbeddingError on provider failure.
        """
        if not chunks:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embed_texts(texts)

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Batch-embed raw strings into float vectors.
        """
        if not texts:
            return []

        try:
            # Check if model router provides embedding handles
            if self._model_router is not None and hasattr(self._model_router, "embed"):
                res = await self._model_router.embed(texts)
                if isinstance(res, list):
                    return res

            # Run in thread pool to avoid blocking the asyncio loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_encode_batch, texts)
        except Exception as e:
            logger.error("embedding_error", count=len(texts), error=str(e))
            raise EmbeddingError(f"Embedding error: {e}") from e

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query string.
        """
        results = await self.embed_texts([query])
        if not results:
            raise EmbeddingError("Empty embedding result for query")
        return results[0]

    def _sync_encode_batch(self, texts: list[str]) -> list[list[float]]:
        model = _get_embedding_model()
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            encoded = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            all_embeddings.extend(encoded.tolist())

        return all_embeddings


class EmbeddingError(Exception):
    """Raised when the embedding provider returns an error."""
