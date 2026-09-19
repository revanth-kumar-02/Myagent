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

from typing import Any, AsyncIterator

import httpx
import structlog

from config import settings
from models.types import GenerationResult

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api-inference.huggingface.co"
_TIMEOUT = 60.0


class HuggingFaceProvider:
    """
    Provider for HuggingFace hosted Inference API.
    Used for Qwen (chat/reasoning/coding) and BGE (embeddings).
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_token}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )

    async def chat_stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
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
        messages: list[dict[str, Any]],
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
