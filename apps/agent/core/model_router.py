"""
core.model_router — Model Router & Failover Coordinator

Responsibilities:
  - Accept a capability tag: "chat", "reason", "code", "vision", "audio", "embedding"
  - Look up the appropriate model entry in the ModelRegistry (loaded from registry.yaml)
  - Return a configured ModelHandle with primary (HuggingFace) and fallback (Ollama) providers
  - Coordinate provider health, online/offline detection, and automatic recovery
  - Never expose or hardcode model IDs in Python source files
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from models.failover import ProviderFailoverManager
from models.providers.huggingface import HuggingFaceProvider
from models.providers.ollama import OllamaProvider
from models.registry import ModelNotFoundError, ModelRegistry
from models.types import ModelCapability, ModelConfig, ModelHandle

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class ModelUnavailableError(Exception):
    """Raised when no model is registered for the requested capability."""


class ModelRouter:
    """
    Routes capability requests to the correct model config and provider handle with failover.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        default_provider: Any | None = None,
        ollama_provider: Any | None = None,
        failover_manager: ProviderFailoverManager | None = None,
    ) -> None:
        self._registry = registry
        self._default_provider = default_provider or HuggingFaceProvider()
        self._ollama_provider = ollama_provider or OllamaProvider()
        self.failover_manager = failover_manager or ProviderFailoverManager(
            hf_provider=self._default_provider,
            ollama_provider=self._ollama_provider,
        )

    async def select(self, capability: ModelCapability | str) -> ModelHandle:
        """
        Return a ModelHandle for the given capability tag.
        Raises ModelUnavailableError if no model is registered for the capability.
        """
        try:
            config = self._registry.get_by_capability(capability)  # type: ignore[arg-type]
            fallback_config = None
            try:
                fallback_config = self._registry.get_by_name("ollama-chat")
            except Exception:
                pass

            logger.debug(
                "model_routed",
                capability=capability,
                model_name=config.name,
                active_provider=self.failover_manager.active_provider_name,
            )
            return ModelHandle(
                config=config,
                provider=self._default_provider,
                fallback_config=fallback_config,
                fallback_provider=self._ollama_provider,
                failover_manager=self.failover_manager,
            )
        except (ModelNotFoundError, KeyError) as e:
            logger.warning("model_unavailable_for_capability", capability=capability, error=str(e))
            raise ModelUnavailableError(f"No model registered for capability: {capability!r}") from e

    async def select_embedding(self) -> ModelHandle:
        """Convenience: return the embedding model handle."""
        return await self.select("embedding")

    def get_config(self, capability: ModelCapability | str) -> ModelConfig:
        """Synchronously return ModelConfig for a capability."""
        try:
            if self.failover_manager and self.failover_manager.active_provider_name == "ollama":
                try:
                    return self._registry.get_by_name("ollama-chat")
                except Exception:
                    pass
            return self._registry.get_by_capability(capability)  # type: ignore[arg-type]
        except ModelNotFoundError as e:
            raise ModelUnavailableError(f"No model registered for capability: {capability!r}") from e
