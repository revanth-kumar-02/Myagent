"""
models.providers.huggingface — HuggingFace Provider

Responsibilities:
  - Communicate with the HuggingFace Inference API
  - Support: chat completion (streaming), text embeddings
  - Handle rate limiting, retries, and timeout
  - Never expose model IDs to callers — always receive them from ModelRegistry

API used:
  - Chat/completion: POST /models/{model_id}/v1/chat/completions (OpenAI-compat)
  - Embeddings:      POST /pipeline/feature-extraction/{model_id}
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx
import structlog

from config import settings
from models.types import GenerationResult

logger = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
_MAX_RETRIES = 3


class HuggingFaceProvider:
    """
    Async HTTP client for the HuggingFace Inference API.
    One provider instance is shared across all model calls.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.huggingface_base_url,
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_token}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )

    async def chat_stream(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion tokens from the HuggingFace OpenAI-compatible endpoint.
        Yields token delta strings.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def chat_complete(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        """Non-streaming chat completion. Returns full result."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def embed(
        self,
        model_id: str,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Returns a list of float vectors (one per input text).
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def close(self) -> None:
        await self._client.aclose()
