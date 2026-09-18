"""
rag.embedder — Central Embedding Pipeline (RAG V2)

Responsibilities:
  - BaseEmbedder abstract interface for modular embedding providers
  - Batch-embed chunks and text strings
  - Robust retry handling with exponential backoff
  - Consistent embedding dimension enforcement
  - Guard against embedding secrets / private keys / credentials

Embedding model is loaded lazily as a process-level singleton.
Model ID and dimensions are configurable via settings.
"""

from __future__ import annotations

import abc
import asyncio
import random
import re
from typing import Any

import structlog

from config import settings
from rag.types import Chunk

logger = structlog.get_logger(__name__)

_MODEL_INSTANCE: Any = None
_DEFAULT_EMBEDDING_DIM = 1024

# Sensitive token / key patterns to protect against embedding secrets
_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN[ A-Z0-9_\-]+KEY-----", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token|password)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{16,}['\"]", re.IGNORECASE),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{32,}", re.IGNORECASE),
]


def is_sensitive_content(text: str) -> bool:
    """Check if text contains obvious secrets, private keys, or credential tokens."""
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


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


class BaseEmbedder(abc.ABC):
    """Abstract interface for embedding services."""

    @abc.abstractmethod
    async def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """Embed a list of Chunks in-place."""
        ...

    @abc.abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed raw strings into float vectors."""
        ...

    @abc.abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Embed a search query string."""
        ...


class EmbeddingService(BaseEmbedder):
    """
    Central embedding service with batching, retries, exponential backoff,
    dimension validation, and secret masking.
    """

    def __init__(
        self,
        model_router: object | None = None,
        expected_dim: int = _DEFAULT_EMBEDDING_DIM,
        max_retries: int = 3,
        initial_retry_delay: float = 0.5,
    ) -> None:
        self._model_router = model_router
        self._batch_size = getattr(settings, "rag_embedding_batch_size", 32)
        self.expected_dim = expected_dim
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay

    async def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Embed a list of Chunks in batches with retry and secret validation.
        """
        if not chunks:
            return []

        # Filter or sanitize any chunk containing raw secret keys
        texts_to_embed: list[str] = []
        indices_to_embed: list[int] = []

        for idx, chunk in enumerate(chunks):
            if is_sensitive_content(chunk.content):
                logger.warning("secret_pattern_detected_skipping_embedding", path=chunk.file_path, idx=chunk.chunk_index)
                chunk.embedding = None
            else:
                texts_to_embed.append(chunk.content)
                indices_to_embed.append(idx)

        if not texts_to_embed:
            return chunks

        embeddings = await self.embed_texts(texts_to_embed)

        for chunk_idx, emb in zip(indices_to_embed, embeddings):
            # Validate embedding dimension
            if len(emb) != self.expected_dim:
                logger.warning(
                    "embedding_dimension_mismatch",
                    expected=self.expected_dim,
                    actual=len(emb),
                )
            chunks[chunk_idx].embedding = emb

        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Batch-embed raw strings into float vectors with retry/exponential backoff.
        """
        if not texts:
            return []

        last_err: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # 1. Check if model router handles embeddings
                if self._model_router is not None and hasattr(self._model_router, "embed"):
                    res = await self._model_router.embed(texts)
                    if isinstance(res, list) and len(res) == len(texts):
                        self._validate_embeddings(res)
                        return res

                # 2. Local SentenceTransformer execution in executor
                loop = asyncio.get_running_loop()
                embeddings = await loop.run_in_executor(None, self._sync_encode_batch, texts)
                self._validate_embeddings(embeddings)
                return embeddings

            except Exception as e:
                last_err = e
                logger.warning(
                    "embedding_attempt_failed",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                if attempt < self.max_retries:
                    # Exponential backoff with random jitter
                    delay = self.initial_retry_delay * (2 ** (attempt - 1)) + random.uniform(0.05, 0.2)
                    await asyncio.sleep(delay)

        raise EmbeddingError(f"Embedding failed after {self.max_retries} retries: {last_err}") from last_err

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query string.
        """
        if not query.strip():
            raise EmbeddingError("Cannot embed empty query string")

        results = await self.embed_texts([query])
        if not results or len(results[0]) == 0:
            raise EmbeddingError("Empty embedding vector returned for query")
        return results[0]

    def _sync_encode_batch(self, texts: list[str]) -> list[list[float]]:
        model = _get_embedding_model()
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            encoded = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            all_embeddings.extend(encoded.tolist())

        return all_embeddings

    def _validate_embeddings(self, embeddings: list[list[float]]) -> None:
        """Ensure all returned embeddings are non-empty and uniform."""
        if not embeddings:
            return
        first_len = len(embeddings[0])
        for emb in embeddings:
            if len(emb) != first_len or any(x is None for x in emb):
                raise EmbeddingError("Malformed or irregular embedding vector returned")


class EmbeddingError(Exception):
    """Raised when the embedding provider returns an error."""
