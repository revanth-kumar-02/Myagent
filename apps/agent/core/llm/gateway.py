import logging
import time
from typing import Dict, Any, Type, TypeVar, Optional, List, Union
from pydantic import BaseModel

from core.llm.registry import ModelRole, ModelConfig
from core.llm.router import ModelRouter, model_router
from core.llm.providers.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMInferenceError,
    LLMResponse
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMProviderGateway:
    """
    Central LLM Gateway.
    All text reasoning and multimodal calls from Agent Core pass through this gateway.
    
    Flow:
    Agent -> LLM Gateway -> Model Router -> Hugging Face Provider -> HF Model
    """

    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router or model_router

    async def generate_text(
        self,
        prompt: str,
        role: Union[str, ModelRole] = ModelRole.CHAT,
        system_prompt: Optional[str] = None,
        profile: str = "primary",
        **kwargs
    ) -> str:
        """
        Generates text using the model resolved for the specified functional role.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        start_time = time.time()
        try:
            result = await provider.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                model_config=model_config,
                **kwargs
            )
            duration = time.time() - start_time
            logger.debug(f"[LLMGateway] Text generated via role='{role}' (model='{model_config.model_id}') in {duration:.2f}s")
            return result
        except LLMProviderError as e:
            logger.error(f"[LLMGateway] Provider error in role='{role}': {e}")
            raise

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        role: Union[str, ModelRole] = ModelRole.REASONING,
        system_prompt: Optional[str] = None,
        profile: str = "primary",
        **kwargs
    ) -> T:
        """
        Generates structured Pydantic model response using the reasoning/planning role.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        start_time = time.time()
        try:
            result = await provider.generate_structured(
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                model_config=model_config,
                **kwargs
            )
            duration = time.time() - start_time
            logger.debug(f"[LLMGateway] Structured {schema.__name__} generated via role='{role}' in {duration:.2f}s")
            return result
        except LLMProviderError as e:
            logger.error(f"[LLMGateway] Structured generation error in role='{role}': {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, str]],
        role: Union[str, ModelRole] = ModelRole.CHAT,
        profile: str = "primary",
        **kwargs
    ) -> str:
        """
        Multi-turn chat completion using the designated chat role model.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        return await provider.chat(messages=messages, model_config=model_config, **kwargs)

    async def understand_vision(
        self,
        image_bytes: bytes,
        prompt: str,
        role: Union[str, ModelRole] = ModelRole.VISION,
        profile: str = "primary",
        **kwargs
    ) -> str:
        """
        Multimodal visual reasoning for screenshots and images.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        return await provider.understand_vision(
            image_bytes=image_bytes,
            prompt=prompt,
            model_config=model_config,
            **kwargs
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        role: Union[str, ModelRole] = ModelRole.SPEECH_TO_TEXT,
        profile: str = "primary",
        **kwargs
    ) -> str:
        """
        Transcribes speech audio using the speech-to-text role model.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        return await provider.transcribe_audio(
            audio_bytes=audio_bytes,
            model_config=model_config,
            **kwargs
        )

    async def synthesize_speech(
        self,
        text: str,
        role: Union[str, ModelRole] = ModelRole.TEXT_TO_SPEECH,
        profile: str = "primary",
        **kwargs
    ) -> bytes:
        """
        Synthesizes text into speech audio bytes.
        """
        provider, model_config = self.router.route(role=role, profile=profile)
        return await provider.synthesize_speech(
            text=text,
            model_config=model_config,
            **kwargs
        )

    @classmethod
    def get_provider(
        cls,
        provider_type: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        role: Union[str, ModelRole] = ModelRole.REASONING
    ) -> BaseLLMProvider:
        """
        Backward-compatible factory method returning the active routed provider.
        """
        provider, _ = model_router.route(role=role)
        return provider

llm_gateway = LLMProviderGateway()
