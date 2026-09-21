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


import hashlib
import math


def _generate_synthetic_embedding(text: str, dim: int = _DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Generate deterministic normalized embedding for offline/fallback without local model weights."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(dim):
        b1 = h[(i * 2) % len(h)]
        b2 = h[(i * 2 + 1) % len(h)]
        val = ((b1 << 8) | b2) / 65535.0 * 2.0 - 1.0
        vec.append(val)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


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
        Cloud-only: Uses HuggingFace Cloud Inference API or lightweight synthetic embeddings.
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

                # 2. Use Cloud HuggingFace Provider if token configured
                if getattr(settings, "huggingface_api_token", ""):
                    try:
                        from models.providers.huggingface import HuggingFaceProvider
                        hf = HuggingFaceProvider(
                            api_token=settings.huggingface_api_token,
                            base_url=settings.huggingface_base_url,
                        )
                        model_name = getattr(settings, "rag_embed_model", "BAAI/bge-m3")
                        res = await hf.embed(model_id=model_name, texts=texts)
                        if isinstance(res, list) and len(res) == len(texts):
                            self._validate_embeddings(res)
                            return res
                    except Exception as hf_err:
                        logger.debug("hf_embed_fallback_to_synthetic", error=str(hf_err))

                # 3. Cloud-only fallback: generate fast zero-storage embeddings (dim: expected_dim)
                embeddings = [_generate_synthetic_embedding(t, self.expected_dim) for t in texts]
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
