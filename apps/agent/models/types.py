"""
models.types — Model system type definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

# Capability tags — the ONLY way agent components reference models
ModelCapability = Literal["chat", "reason", "code", "vision", "audio", "embedding"]


@dataclass
class ModelConfig:
    """
    A single model entry from the registry.
    Loaded from registry.yaml; never constructed manually.
    """
    name: str                        # registry key (e.g. "qwen-chat")
    provider: Literal["huggingface"]
    model_id: str                    # actual HuggingFace model ID
    capabilities: list[ModelCapability]
    context_window: int
    dimension: int | None = None     # only for embedding models


@dataclass
class GenerationResult:
    full_text: str
    input_tokens: int
    output_tokens: int
    model_id: str
    latency_ms: int = 0


class ModelHandle:
    """
    A resolved, ready-to-use model reference.
    Obtained from ModelRouter.select(capability).
    """

    def __init__(self, config: ModelConfig, provider: Any) -> None:
        self.config = config
        self._provider = provider

    async def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> GenerationResult:
        """Non-streaming generation. Returns full GenerationResult."""
        if hasattr(self._provider, "chat_complete"):
            res: GenerationResult = await self._provider.chat_complete(
                model_id=self.config.model_id,
                messages=messages,
                **kwargs,
            )
            return res
        raise NotImplementedError(f"Provider {type(self._provider)} does not support chat_complete")

    async def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        """Streaming generation. Yields token deltas."""
        if hasattr(self._provider, "chat_stream"):
            async for chunk in self._provider.chat_stream(
                model_id=self.config.model_id,
                messages=messages,
                **kwargs,
            ):
                yield chunk
        else:
            raise NotImplementedError(f"Provider {type(self._provider)} does not support chat_stream")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding. Returns a list of float vectors."""
        if hasattr(self._provider, "embed"):
            res: list[list[float]] = await self._provider.embed(
                model_id=self.config.model_id,
                texts=texts,
            )
            return res
        raise NotImplementedError(f"Provider {type(self._provider)} does not support embed")

