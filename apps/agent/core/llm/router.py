import os
import logging
from typing import Optional, Union, Dict, Any

from core.llm.registry import ModelRegistry, ModelConfig, ModelRole, model_registry
from core.llm.providers.base import (
    BaseLLMProvider,
    LLMInvalidModelError,
    LLMRoleUnavailableError,
    LLMDisabledRoleError,
    LLMUnsupportedTaskError
)
from core.llm.providers.huggingface import HuggingFaceProvider
from core.llm.providers.rule_based import RuleBasedLLMProvider

logger = logging.getLogger(__name__)

class ModelRouter:
    """
    Decoupled Model Router.
    Agent components request a functional capability/role (e.g. 'chat', 'reasoning', 'coding', 'vision'),
    NOT raw provider model IDs.
    
    Flow:
    Agent Core -> Model Router -> Model Registry -> Selected model_id -> Hugging Face Provider -> Inference
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        hf_provider: Optional[HuggingFaceProvider] = None,
        fallback_provider: Optional[RuleBasedLLMProvider] = None
    ):
        self.registry = registry or model_registry
        self._hf_provider = hf_provider or HuggingFaceProvider()
        self._fallback_provider = fallback_provider or RuleBasedLLMProvider()

    def get_model(
        self,
        role: Union[str, ModelRole],
        profile: str = "primary",
        capability: Optional[str] = None
    ) -> ModelConfig:
        """
        Resolves a functional role to its active ModelConfig from the registry.
        Validates that:
        - Role is supported
        - Model exists in registry
        - Model is enabled
        - Model ID is configured
        - Requested capability is supported
        Raises structured LLMRoleUnavailableError / LLMDisabledRoleError if invalid.
        """
        config = self.registry.get_model_config(role=role, profile=profile)
        self.registry.validate_model_config(config, role=role, capability=capability)
        return config

    def get_provider(
        self,
        role: Union[str, ModelRole],
        profile: str = "primary"
    ) -> BaseLLMProvider:
        """
        Returns the appropriate provider instance for the requested role.
        If Hugging Face credentials are not available, gracefully uses the RuleBased fallback.
        """
        # Check if HF token is present
        if not self._hf_provider._token or self._hf_provider._token in ("none", "sk-placeholder", "placeholder"):
            logger.debug(f"[ModelRouter] HF_TOKEN unconfigured. Routing role '{role}' to RuleBasedLLMProvider.")
            return self._fallback_provider

        return self._hf_provider

    def route(
        self,
        role: Union[str, ModelRole],
        profile: str = "primary",
        capability: Optional[str] = None
    ) -> tuple[BaseLLMProvider, ModelConfig]:
        """
        Convenience router method returning both the resolved provider and ModelConfig.
        """
        model_config = self.get_model(role, profile=profile, capability=capability)
        provider = self.get_provider(role, profile=profile)
        return provider, model_config

model_router = ModelRouter()
