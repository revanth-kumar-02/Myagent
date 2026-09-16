import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, TypeVar, Optional, List, Union
from pydantic import BaseModel, Field
from core.llm.registry import ModelConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ─── Structured Exception Hierarchy ───────────────────────────────────────────

class LLMProviderError(Exception):
    """Base error for all LLM inference and provider failures."""
    def __init__(self, message: str, provider: str = "unknown", model_id: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.model_id = model_id

class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication fails (missing or invalid API key/token)."""
    pass

class LLMInvalidModelError(LLMProviderError):
    """Raised when the specified model ID does not exist or is not accessible."""
    pass

class LLMUnsupportedTaskError(LLMProviderError):
    """Raised when the model does not support the requested task (e.g. text model asked to transcribe audio)."""
    pass

class LLMRateLimitError(LLMProviderError):
    """Raised when the provider rate limit or quota is exceeded."""
    pass

class LLMTimeoutError(LLMProviderError):
    """Raised when the inference request times out."""
    pass

class LLMInferenceError(LLMProviderError):
    """Raised when the inference provider returns a non-200 failure or malformed payload."""
    pass

# ─── Usage & Telemetry ─────────────────────────────────────────────────────────

class LLMUsage(BaseModel):
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0

class LLMResponse(BaseModel):
    content: str
    role: str
    model_id: str
    provider: str
    duration_seconds: float = 0.0
    usage: Optional[LLMUsage] = None

# ─── Base Provider Abstraction ─────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """Provider-independent interface for all inference backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g. 'huggingface', 'rule_based')."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        """Generates plain text response for given prompt and optional system prompt."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> T:
        """Generates structured response validated against a Pydantic schema."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        """Multi-turn chat completion from structured message array."""
        pass

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        """Transcribes audio speech into text. Subclasses override if supported."""
        raise LLMUnsupportedTaskError(
            f"Provider '{self.name}' does not support audio transcription.",
            provider=self.name,
            model_id=model_config.model_id if model_config else None
        )

    async def synthesize_speech(
        self,
        text: str,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> bytes:
        """Synthesizes text into audio speech bytes. Subclasses override if supported."""
        raise LLMUnsupportedTaskError(
            f"Provider '{self.name}' does not support speech synthesis.",
            provider=self.name,
            model_id=model_config.model_id if model_config else None
        )

    async def understand_vision(
        self,
        image_bytes: bytes,
        prompt: str,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        """Analyzes image content with text prompt. Subclasses override if supported."""
        raise LLMUnsupportedTaskError(
            f"Provider '{self.name}' does not support vision understanding.",
            provider=self.name,
            model_id=model_config.model_id if model_config else None
        )
