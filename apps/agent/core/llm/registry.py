import os
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from config import settings

logger = logging.getLogger(__name__)

class ModelRole(str, Enum):
    CHAT = "chat"
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"

class ModelProfile(str, Enum):
    PRIMARY = "primary"
    FALLBACK = "fallback"
    FAST = "fast"
    DEEP = "deep"

class ModelConfig(BaseModel):
    model_id: str = Field(description="Hugging Face model repository ID")
    provider: str = Field(default="huggingface", description="Inference provider name")
    role: ModelRole = Field(description="Functional role of the model")
    profile: str = Field(default="primary", description="Profile slot: primary | fallback | fast | deep")
    capabilities: List[str] = Field(default_factory=list, description="Supported capabilities, e.g. chat, structured_output, streaming")
    task: str = Field(default="text-generation", description="HF task type, e.g. text-generation, automatic-speech-recognition")
    context_limit: Optional[int] = Field(default=32768, description="Maximum context window in tokens")
    temperature_default: float = Field(default=0.2, description="Default sampling temperature")
    max_tokens_default: int = Field(default=4096, description="Default max new tokens")
    timeout_seconds: float = Field(default=60.0, description="Inference request timeout in seconds")
    supports_streaming: bool = Field(default=True, description="Whether the model supports token streaming")
    supports_tool_calling: bool = Field(default=False, description="Whether the model supports function/tool calling")
    supports_vision: bool = Field(default=False, description="Whether the model accepts visual/image input")
    enabled: bool = Field(default=True, description="Whether this model is active")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific parameters")

# Required capabilities per task type
TASK_CAPABILITY_MAP: Dict[str, List[str]] = {
    "text-generation": ["chat", "text_generation", "structured_output"],
    "automatic-speech-recognition": ["speech_to_text", "transcription"],
    "text-to-speech": ["text_to_speech", "voice_synthesis"],
    "image-to-text": ["vision", "image_understanding"],
    "visual-question-answering": ["vision", "image_understanding"]
}

class ModelRegistry:
    """
    Centralized Model Configuration & Registry.
    Ensures model IDs are strictly configuration-driven and decoupling Agent Core
    from provider-specific IDs.
    """

    def __init__(self):
        # Role -> Profile -> ModelConfig
        self._registry: Dict[ModelRole, Dict[str, ModelConfig]] = {}
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Loads model registry configurations from environment variables or settings."""
        # Read from environment/settings with sensible default HF models
        chat_model = (
            os.getenv("HF_CHAT_MODEL")
            or getattr(settings, "HF_CHAT_MODEL", None)
            or os.getenv("LLM_MODEL")
            or "meta-llama/Llama-3.3-70B-Instruct"
        )
        reasoning_model = (
            os.getenv("HF_REASONING_MODEL")
            or getattr(settings, "HF_REASONING_MODEL", None)
            or "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
        )
        coding_model = (
            os.getenv("HF_CODING_MODEL")
            or getattr(settings, "HF_CODING_MODEL", None)
            or "Qwen/Qwen2.5-Coder-32B-Instruct"
        )
        vision_model = (
            os.getenv("HF_VISION_MODEL")
            or getattr(settings, "HF_VISION_MODEL", None)
            or "meta-llama/Llama-3.2-11B-Vision-Instruct"
        )
        stt_model = (
            os.getenv("HF_STT_MODEL")
            or getattr(settings, "HF_STT_MODEL", None)
            or "openai/whisper-large-v3"
        )
        tts_model = (
            os.getenv("HF_TTS_MODEL")
            or getattr(settings, "HF_TTS_MODEL", None)
            or "facebook/mms-tts-eng"
        )

        hf_provider = os.getenv("HF_PROVIDER") or getattr(settings, "HF_PROVIDER", "huggingface")

        # 1. Chat Model (Primary)
        self.register_model(
            ModelConfig(
                model_id=chat_model,
                provider=hf_provider,
                role=ModelRole.CHAT,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["chat", "text_generation", "streaming", "structured_output"],
                task="text-generation",
                context_limit=131072,
                temperature_default=0.7,
                max_tokens_default=4096,
                supports_streaming=True,
                supports_tool_calling=True
            )
        )

        # 2. Reasoning Model (Primary) - Planning, Analysis, Verification
        self.register_model(
            ModelConfig(
                model_id=reasoning_model,
                provider=hf_provider,
                role=ModelRole.REASONING,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["reasoning", "chat", "text_generation", "structured_output"],
                task="text-generation",
                context_limit=131072,
                temperature_default=0.2,
                max_tokens_default=8192,
                supports_streaming=True
            )
        )

        # 3. Coding Model (Primary) - Code Generation & Debugging
        self.register_model(
            ModelConfig(
                model_id=coding_model,
                provider=hf_provider,
                role=ModelRole.CODING,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["coding", "text_generation", "structured_output"],
                task="text-generation",
                context_limit=131072,
                temperature_default=0.1,
                max_tokens_default=8192,
                supports_streaming=True
            )
        )

        # 4. Vision Model (Primary) - Screenshot & Image Understanding
        self.register_model(
            ModelConfig(
                model_id=vision_model,
                provider=hf_provider,
                role=ModelRole.VISION,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["vision", "image_understanding", "chat"],
                task="image-to-text",
                context_limit=131072,
                temperature_default=0.2,
                max_tokens_default=4096,
                supports_vision=True
            )
        )

        # 5. Speech-to-Text Model (Primary) - Audio Transcription
        self.register_model(
            ModelConfig(
                model_id=stt_model,
                provider=hf_provider,
                role=ModelRole.SPEECH_TO_TEXT,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["speech_to_text", "transcription"],
                task="automatic-speech-recognition",
                timeout_seconds=90.0
            )
        )

        # 6. Text-to-Speech Model (Primary) - Spoken Responses
        self.register_model(
            ModelConfig(
                model_id=tts_model,
                provider=hf_provider,
                role=ModelRole.TEXT_TO_SPEECH,
                profile=ModelProfile.PRIMARY.value,
                capabilities=["text_to_speech", "voice_synthesis"],
                task="text-to-speech",
                timeout_seconds=60.0
            )
        )

    def register_model(self, config: ModelConfig) -> None:
        """Registers a model configuration under its specified role and profile."""
        if config.role not in self._registry:
            self._registry[config.role] = {}
        self._registry[config.role][config.profile] = config
        logger.debug(f"[ModelRegistry] Registered {config.role.value}:{config.profile} -> {config.model_id}")

    def get_model_config(
        self,
        role: Union[str, ModelRole],
        profile: str = "primary"
    ) -> Optional[ModelConfig]:
        """Resolves the active ModelConfig for a given role and profile slot."""
        if isinstance(role, str):
            try:
                role_enum = ModelRole(role.lower())
            except ValueError:
                logger.warning(f"[ModelRegistry] Unknown model role string: '{role}'")
                return None
        else:
            role_enum = role

        profiles = self._registry.get(role_enum, {})
        if profile in profiles and profiles[profile].enabled:
            return profiles[profile]

        # Fallback to primary if requested profile is not found but primary exists
        if "primary" in profiles and profiles["primary"].enabled:
            return profiles["primary"]

        return None

    def list_roles(self) -> List[str]:
        """Returns all configured model roles."""
        return [r.value for r in self._registry.keys()]

    def list_models_for_role(self, role: Union[str, ModelRole]) -> Dict[str, ModelConfig]:
        """Returns all profile slots (primary, fallback, fast, deep) for a role."""
        if isinstance(role, str):
            try:
                role_enum = ModelRole(role.lower())
            except ValueError:
                return {}
        else:
            role_enum = role
        return dict(self._registry.get(role_enum, {}))

    def validate_capability(self, config: ModelConfig, capability: str) -> bool:
        """Validates that a model configuration supports the requested capability."""
        return capability in config.capabilities

    def validate_task_compatibility(self, config: ModelConfig, requested_task: str) -> bool:
        """Validates that the model's configured task matches the requested operation."""
        return config.task == requested_task or requested_task in config.capabilities

model_registry = ModelRegistry()
