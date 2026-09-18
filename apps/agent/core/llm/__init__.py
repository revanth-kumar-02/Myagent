from core.llm.registry import (
    ModelRole,
    ModelProfile,
    ModelConfig,
    ModelRegistry,
    model_registry,
    TASK_CAPABILITY_MAP
)
from core.llm.router import (
    ModelRouter,
    model_router
)
from core.llm.providers.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMAuthenticationError,
    LLMInvalidModelError,
    LLMRoleUnavailableError,
    LLMDisabledRoleError,
    LLMUnsupportedTaskError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInferenceError,
    LLMResponse,
    LLMUsage
)
from core.llm.providers.huggingface import HuggingFaceProvider
from core.llm.providers.rule_based import RuleBasedLLMProvider
from core.llm.gateway import (
    LLMProviderGateway,
    llm_gateway
)

# Backward-compatibility alias for legacy imports
GroqProvider = HuggingFaceProvider

__all__ = [
    "ModelRole",
    "ModelProfile",
    "ModelConfig",
    "ModelRegistry",
    "model_registry",
    "TASK_CAPABILITY_MAP",
    "ModelRouter",
    "model_router",
    "BaseLLMProvider",
    "LLMProviderError",
    "LLMAuthenticationError",
    "LLMInvalidModelError",
    "LLMRoleUnavailableError",
    "LLMDisabledRoleError",
    "LLMUnsupportedTaskError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMInferenceError",
    "LLMResponse",
    "LLMUsage",
    "HuggingFaceProvider",
    "RuleBasedLLMProvider",
    "LLMProviderGateway",
    "llm_gateway",
    "GroqProvider"
]
