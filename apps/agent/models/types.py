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


class ModelHandle:
    """
    A resolved, ready-to-use model reference.
    Obtained from ModelRouter.select(capability).
    """

    def __init__(self, config: ModelConfig, provider: object) -> None:
        self.config = config
        self._provider = provider

    async def generate(self, messages: list[dict[str, Any]], **kwargs: object) -> GenerationResult:
        """Non-streaming generation. Returns full text when complete."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def stream(self, messages: list[dict[str, Any]], **kwargs: object) -> AsyncIterator[str]:
        """Streaming generation. Yields token deltas."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding. Returns a list of float vectors."""
        raise NotImplementedError  # TODO: implement in feature phase
