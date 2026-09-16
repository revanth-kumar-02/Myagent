import os
import json
import time
import base64
import logging
import httpx
from typing import Dict, Any, Type, TypeVar, Optional, List, Union
from pydantic import BaseModel

from config import settings
from core.llm.registry import ModelConfig, ModelRole
from core.llm.providers.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMAuthenticationError,
    LLMInvalidModelError,
    LLMUnsupportedTaskError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInferenceError,
    LLMResponse,
    LLMUsage
)
from core.observability import record_fallback_event

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class HuggingFaceProvider(BaseLLMProvider):
    """
    Production Hugging Face Inference Provider.
    Supports chat completions router, task-specific inference, multimodal vision,
    speech-to-text (Whisper), and text-to-speech.
    Never exposes or logs HF_TOKEN.
    """

    def __init__(self, token: Optional[str] = None):
        raw_token = (
            token
            or os.getenv("HF_TOKEN")
            or getattr(settings, "HF_TOKEN", None)
            or os.getenv("HUGGINGFACE_API_KEY")
            or os.getenv("HUGGING_FACE_HUB_TOKEN")
        )
        self._token = raw_token.strip() if raw_token else None
        # Router endpoint for OpenAI-compatible chat completions
        self._chat_router_url = "https://api-inference.huggingface.co/v1/chat/completions"
        self._model_base_url = "https://api-inference.huggingface.co/models"

    @property
    def name(self) -> str:
        return "huggingface"

    def _get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        """Builds authenticated headers while keeping token strictly unlogged."""
        if not self._token or self._token in ("none", "sk-placeholder", "placeholder"):
            raise LLMAuthenticationError(
                "Hugging Face token is missing or unconfigured. Please set HF_TOKEN.",
                provider=self.name
            )
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": content_type
        }

    def _mask_token(self) -> str:
        """Returns masked token string for safe diagnostics."""
        if not self._token:
            return "<none>"
        if len(self._token) <= 8:
            return "***"
        return f"{self._token[:4]}****{self._token[-4:]}"

    def _validate_task(self, model_config: Optional[ModelConfig], expected_task: str):
        """Validates model task compatibility before execution."""
        if model_config and model_config.task and model_config.task != expected_task:
            # Check if task is in capabilities as fallback
            if expected_task not in model_config.capabilities:
                raise LLMUnsupportedTaskError(
                    f"Model '{model_config.model_id}' (task: '{model_config.task}') does not support '{expected_task}'.",
                    provider=self.name,
                    model_id=model_config.model_id
                )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, model_config=model_config, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        model_id = model_config.model_id if model_config else "meta-llama/Llama-3.3-70B-Instruct"
        timeout = kwargs.get("timeout") or (model_config.timeout_seconds if model_config else 60.0)
        temperature = kwargs.get("temperature", model_config.temperature_default if model_config else 0.2)
        max_tokens = kwargs.get("max_tokens", model_config.max_tokens_default if model_config else 4096)

        headers = self._get_headers()
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        start_time = time.time()
        logger.debug(f"[HuggingFaceProvider] Dispatching chat completion to {model_id} (timeout: {timeout}s)")

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                # 1. Try OpenAI-compatible chat router
                res = await client.post(self._chat_router_url, headers=headers, json=payload)
                
                # If router returns 404 or unsupported for this model, fallback to direct model pipeline
                if res.status_code == 404:
                    return await self._fallback_model_pipeline(client, model_id, messages, headers, timeout, temperature, max_tokens)

                if res.status_code in (401, 403):
                    raise LLMAuthenticationError(
                        f"Hugging Face authentication failed (status {res.status_code}). Check HF_TOKEN.",
                        provider=self.name,
                        model_id=model_id
                    )
                if res.status_code == 429:
                    raise LLMRateLimitError(
                        f"Hugging Face rate limit exceeded for model '{model_id}'.",
                        provider=self.name,
                        model_id=model_id
                    )
                if res.status_code != 200:
                    raise LLMInferenceError(
                        f"Hugging Face API returned status {res.status_code}: {res.text[:300]}",
                        provider=self.name,
                        model_id=model_id
                    )

                data = res.json()
                content = data["choices"][0]["message"]["content"]
                duration = time.time() - start_time
                logger.debug(f"[HuggingFaceProvider] Received {len(content)} chars in {duration:.2f}s")
                return content

            except httpx.TimeoutException:
                raise LLMTimeoutError(
                    f"Hugging Face request timed out after {timeout}s for model '{model_id}'.",
                    provider=self.name,
                    model_id=model_id
                )
            except httpx.RequestError as e:
                raise LLMInferenceError(
                    f"Hugging Face network connection error: {str(e)}",
                    provider=self.name,
                    model_id=model_id
                )

    async def _fallback_model_pipeline(
        self,
        client: httpx.AsyncClient,
        model_id: str,
        messages: List[Dict[str, str]],
        headers: Dict[str, str],
        timeout: float,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Fallback to standard HF model endpoint if router endpoint is unavailable."""
        pipeline_url = f"{self._model_base_url}/{model_id}"
        prompt_lines = [f"{m['role'].capitalize()}: {m['content']}" for m in messages]
        full_prompt = "\n".join(prompt_lines) + "\nAssistant:"

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens,
                "return_full_text": False
            }
        }
        res = await client.post(pipeline_url, headers=headers, json=payload)
        if res.status_code != 200:
            raise LLMInferenceError(
                f"Hugging Face pipeline error {res.status_code}: {res.text[:300]}",
                provider=self.name,
                model_id=model_id
            )
        data = res.json()
        if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        elif isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"].strip()
        return str(data)

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        struct_system = (
            f"{system_prompt or 'You are an intelligent reasoning agent.'}\n"
            f"You MUST respond ONLY with a valid JSON object strictly matching this schema:\n"
            f"{schema_json}\n"
            f"Do NOT include markdown block formatting, extra text, or explanations."
        )
        raw_res = await self.generate_text(
            prompt=prompt,
            system_prompt=struct_system,
            model_config=model_config,
            **kwargs
        )

        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            return schema.model_validate(parsed)
        except Exception as e:
            logger.warning(f"[HuggingFaceProvider] JSON validation failed on: {cleaned[:200]}")
            raise LLMInferenceError(
                f"Failed to parse structured response into schema {schema.__name__}: {str(e)}",
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
        model_id = model_config.model_id if model_config else "meta-llama/Llama-3.2-11B-Vision-Instruct"
        timeout = kwargs.get("timeout") or (model_config.timeout_seconds if model_config else 60.0)
        self._validate_task(model_config, "image-to-text")

        headers = self._get_headers()
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{base64_img}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ]
        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 2048)
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(self._chat_router_url, headers=headers, json=payload)
            if res.status_code != 200:
                raise LLMInferenceError(
                    f"Vision inference error (status {res.status_code}): {res.text[:300]}",
                    provider=self.name,
                    model_id=model_id
                )
            data = res.json()
            return data["choices"][0]["message"]["content"]

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        model_id = model_config.model_id if model_config else "openai/whisper-large-v3"
        timeout = kwargs.get("timeout") or (model_config.timeout_seconds if model_config else 90.0)
        self._validate_task(model_config, "automatic-speech-recognition")

        headers = self._get_headers(content_type="audio/wav")
        endpoint = f"{self._model_base_url}/{model_id}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(endpoint, headers=headers, content=audio_bytes)
            if res.status_code != 200:
                raise LLMInferenceError(
                    f"STT inference error (status {res.status_code}): {res.text[:300]}",
                    provider=self.name,
                    model_id=model_id
                )
            data = res.json()
            return data.get("text", "")

    async def synthesize_speech(
        self,
        text: str,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> bytes:
        model_id = model_config.model_id if model_config else "facebook/mms-tts-eng"
        timeout = kwargs.get("timeout") or (model_config.timeout_seconds if model_config else 60.0)
        self._validate_task(model_config, "text-to-speech")

        headers = self._get_headers(content_type="application/json")
        endpoint = f"{self._model_base_url}/{model_id}"
        payload = {"inputs": text}

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            if res.status_code != 200:
                raise LLMInferenceError(
                    f"TTS inference error (status {res.status_code}): {res.text[:300]}",
                    provider=self.name,
                    model_id=model_id
                )
            return res.content
