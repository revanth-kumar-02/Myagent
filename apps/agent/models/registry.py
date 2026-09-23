"""
models.registry — Model Registry

Loads models/registry.yaml at startup and provides a typed lookup API.
This is the only place model_id strings appear in Python code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import yaml
import structlog

from models.types import ModelCapability, ModelConfig

logger = structlog.get_logger(__name__)


class ModelRegistry:
    """
    In-memory model registry loaded from registry.yaml.

    Usage:
        registry = ModelRegistry.load(Path("models/registry.yaml"))
        config = registry.get_by_capability("chat")
    """

    def __init__(self, models: dict[str, ModelConfig]) -> None:
        self._models = models

    @classmethod
    def load(cls, path: Path) -> "ModelRegistry":
        """Load and parse registry.yaml. Raises on invalid config."""
        with path.open() as f:
            raw = yaml.safe_load(f)

        models: dict[str, ModelConfig] = {}
        for name, entry in raw.get("models", {}).items():
            models[name] = ModelConfig(
                name=name,
                provider=entry["provider"],
                model_id=entry["model_id"],
                capabilities=entry.get("capabilities", []),
                context_window=entry.get("context_window", 4096),
                dimension=entry.get("dimension"),
                metadata=entry.get("metadata"),
            )
            logger.info("model_registered", name=name, capabilities=models[name].capabilities)

        return cls(models)

    def get_by_capability(self, capability: ModelCapability) -> ModelConfig:
        """
        Return the first model registered for the given capability.
        Raises ModelNotFoundError if no model matches.
        """
        for config in self._models.values():
            if capability in config.capabilities:
                return config
        raise ModelNotFoundError(f"No model registered for capability: {capability!r}")

    def get_by_name(self, name: str) -> ModelConfig:
        """Return a model config by its registry key."""
        if name not in self._models:
            raise ModelNotFoundError(f"Model not found in registry: {name!r}")
        return self._models[name]

    def all(self) -> Iterator[ModelConfig]:
        """Iterate all registered model configs."""
        yield from self._models.values()


class ModelNotFoundError(Exception):
    """Raised when a model or capability is not found in the registry."""
