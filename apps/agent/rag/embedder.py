"""
rag.embedder — Embedding Service

Responsibilities:
  - Accept a list of Chunks
  - Batch-embed them using the embedding model from the ModelRegistry
  - Attach the resulting vectors to each Chunk
  - Return the annotated Chunks (embedding field populated)

Embedding model is resolved via ModelRouter using capability="embedding".
Model ID is never hardcoded here.
"""

from __future__ import annotations

import structlog

from config import settings
from rag.types import Chunk

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Batch-embeds Chunks using the model registered for the 'embedding' capability.
    """

    def __init__(self, model_router: object) -> None:
        # model_router: core.model_router.ModelRouter — injected to avoid circular import
        self._model_router = model_router
        self._batch_size = settings.rag_embedding_batch_size

    async def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Embed a list of Chunks in batches.

        Modifies chunks in-place (sets chunk.embedding) and returns the list.
        Raises EmbeddingError on provider failure.
        """
        raise NotImplementedError  # TODO: implement in feature phase


class EmbeddingError(Exception):
    """Raised when the embedding provider returns an error."""
