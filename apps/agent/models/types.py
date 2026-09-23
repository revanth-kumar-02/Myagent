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
    provider: Literal["huggingface", "ollama", "mock"] | str
    model_id: str                    # model ID for the provider
    capabilities: list[ModelCapability]
    context_window: int
    dimension: int | None = None     # only for embedding models
    metadata: dict[str, Any] | None = None


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

    def __init__(
        self,
        config: ModelConfig,
        provider: Any,
        fallback_config: ModelConfig | None = None,
        fallback_provider: Any | None = None,
        failover_manager: Any | None = None,
    ) -> None:
        self.config = config
        self._provider = provider
        self.fallback_config = fallback_config
        self._fallback_provider = fallback_provider
        self._failover_manager = failover_manager

    @property
    def active_model_id(self) -> str:
        if self._failover_manager and getattr(self._failover_manager, "active_provider_name", "") == "ollama":
            if self.fallback_config:
                return self.fallback_config.model_id
            return "qwen3:1.7b"
        return self.config.model_id

    async def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> GenerationResult:
        """Non-streaming generation with automatic failover."""
        use_fallback = (
            self._failover_manager is not None
            and getattr(self._failover_manager, "active_provider_name", "") == "ollama"
            and self._fallback_provider is not None
        )
        if use_fallback and self._fallback_provider is not None:
            model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
            res: GenerationResult = await self._fallback_provider.chat_complete(model_id=model_id, messages=messages, **kwargs)
            return res

        try:
            if self._provider is not None and hasattr(self._provider, "chat_complete"):
                res = await self._provider.chat_complete(
                    model_id=self.config.model_id,
                    messages=messages,
                    **kwargs,
                )
                if self._failover_manager:
                    self._failover_manager.record_hf_success()
                return res
        except Exception as e:
            if self._fallback_provider is not None and self._failover_manager is not None:
                self._failover_manager.record_hf_failure(reason=str(e))
                model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
                fallback_res: GenerationResult = await self._fallback_provider.chat_complete(model_id=model_id, messages=messages, **kwargs)
                return fallback_res
            raise

        raise NotImplementedError(f"Provider {type(self._provider)} does not support chat_complete")

    async def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        """Streaming generation with automatic failover before partial commits."""
        use_fallback = (
            self._failover_manager is not None
            and getattr(self._failover_manager, "active_provider_name", "") == "ollama"
            and self._fallback_provider is not None
        )
        if use_fallback and self._fallback_provider is not None:
            model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
            async for chunk in self._fallback_provider.chat_stream(model_id=model_id, messages=messages, **kwargs):
                yield str(chunk)
            return

        yielded_any = False
        try:
            if self._provider is not None and hasattr(self._provider, "chat_stream"):
                async for chunk in self._provider.chat_stream(
                    model_id=self.config.model_id,
                    messages=messages,
                    **kwargs,
                ):
                    yielded_any = True
                    yield str(chunk)
                if self._failover_manager:
                    self._failover_manager.record_hf_success()
                return
        except Exception as e:
            if not yielded_any and self._fallback_provider is not None and self._failover_manager is not None:
                self._failover_manager.record_hf_failure(reason=str(e))
                model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
                async for chunk in self._fallback_provider.chat_stream(model_id=model_id, messages=messages, **kwargs):
                    yield str(chunk)
                return
            raise

        raise NotImplementedError(f"Provider {type(self._provider)} does not support chat_stream")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding. Returns a list of float vectors."""
        if self._provider is not None and hasattr(self._provider, "embed"):
            try:
                res: list[list[float]] = await self._provider.embed(
                    model_id=self.config.model_id,
                    texts=texts,
                )
                return res
            except Exception:
                if self._fallback_provider is not None and hasattr(self._fallback_provider, "embed"):
                    model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
                    f_res: list[list[float]] = await self._fallback_provider.embed(model_id=model_id, texts=texts)
                    return f_res
                raise
        elif self._fallback_provider is not None and hasattr(self._fallback_provider, "embed"):
            model_id = self.fallback_config.model_id if self.fallback_config else "qwen3:1.7b"
            f_res = await self._fallback_provider.embed(model_id=model_id, texts=texts)
            return f_res
        raise NotImplementedError(f"Provider {type(self._provider)} does not support embed")

