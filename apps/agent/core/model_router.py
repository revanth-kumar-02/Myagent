"""
core.model_router — Model Router (V7)

Responsibilities:
  - Accept a capability tag: "chat", "reason", "code", "vision", "audio", "embedding"
  - Look up the appropriate model entry in the ModelRegistry (loaded from registry.yaml)
  - Return a configured provider handle for that model
  - Never expose or hardcode model IDs in Python source files
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from models.registry import ModelNotFoundError, ModelRegistry
from models.types import ModelCapability, ModelConfig, ModelHandle

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class ModelUnavailableError(Exception):
    """Raised when no model is registered for the requested capability."""


class SimpleProviderAdapter:
    """Lightweight provider adapter for model handles."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config


class ModelRouter:
    """
    Routes capability requests to the correct model config and provider handle.
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    async def select(self, capability: ModelCapability | str) -> ModelHandle:
        """
        Return a ModelHandle for the given capability tag.
        Raises ModelUnavailableError if no model is registered for the capability.
        """
        try:
            config = self._registry.get_by_capability(capability)  # type: ignore[arg-type]
            provider = SimpleProviderAdapter(config)
            logger.debug("model_routed", capability=capability, model_name=config.name)
            return ModelHandle(config=config, provider=provider)
        except (ModelNotFoundError, KeyError) as e:
            logger.warning("model_unavailable_for_capability", capability=capability, error=str(e))
            raise ModelUnavailableError(f"No model registered for capability: {capability!r}") from e

    async def select_embedding(self) -> ModelHandle:
        """Convenience: return the embedding model handle."""
        return await self.select("embedding")

    def get_config(self, capability: ModelCapability | str) -> ModelConfig:
        """Synchronously return ModelConfig for a capability."""
        try:
            return self._registry.get_by_capability(capability)  # type: ignore[arg-type]
        except ModelNotFoundError as e:
            raise ModelUnavailableError(f"No model registered for capability: {capability!r}") from e
