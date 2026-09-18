"""
core.model_router — Model Router

Responsibilities:
  - Accept a capability tag (e.g., "chat", "reason", "code", "vision", "audio", "embedding")
  - Look up the appropriate model entry in the ModelRegistry
  - Return a configured provider handle for that model
  - Never expose or hardcode model IDs outside this module

This is the ONLY component that translates capability → model_id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from models.registry import ModelRegistry
    from models.types import ModelCapability, ModelHandle

logger = structlog.get_logger(__name__)


class ModelRouter:
    """
    Routes capability requests to the correct provider + model.

    Usage:
        handle = await router.select("chat")
        async for token in handle.stream(messages):
            ...
    """

    def __init__(self, registry: "ModelRegistry") -> None:
        self._registry = registry

    async def select(self, capability: "ModelCapability") -> "ModelHandle":
        """
        Return a ModelHandle for the given capability tag.
        Raises ModelUnavailableError if no model is registered for the capability.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def select_embedding(self) -> "ModelHandle":
        """Convenience: return the embedding model handle."""
        return await self.select("embedding")  # type: ignore[arg-type]


class ModelUnavailableError(Exception):
    """Raised when no model is registered for the requested capability."""
