"""
models.providers.ollama — Local Ollama LLM Gateway Provider

Responsibilities:
  - Communicate with local Ollama daemon (default: http://127.0.0.1:11434)
  - Support: Native chat completion (POST /api/chat) with streaming and non-streaming
  - Support: Text embeddings (POST /api/embed or POST /api/embeddings)
  - Health check: GET /api/tags to verify daemon and model availability
  - Expose identical interface to HuggingFaceProvider for seamless failover
  - Strict error handling with short health-check timeouts
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import httpx
import structlog

from config import settings
from models.providers.huggingface import (
    LLMAuthError,
    LLMError,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from models.types import GenerationResult

logger = structlog.get_logger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
_DEFAULT_TIMEOUT = 45.0
_HEALTH_TIMEOUT = 3.0


class OllamaProvider:
    """
    Local Ollama inference provider and fallback LLM brain.
    """

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or getattr(settings, "ollama_base_url", None) or _DEFAULT_BASE_URL).rstrip("/")
        self._default_model = default_model or getattr(settings, "ollama_chat_model", "qwen3:1.7b")
        self._timeout = timeout
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout, connect=5.0),
            )
        return self._client

    @staticmethod
    def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize messages for Ollama format."""
        normalized: list[dict[str, Any]] = []
        for msg in messages:
            role = str(msg.get("role", "user")).lower()
            if role not in ("system", "user", "assistant", "tool"):
                role = "user"
            content = str(msg.get("content", ""))
            entry: dict[str, Any] = {"role": role, "content": content}
            if "tool_calls" in msg and msg["tool_calls"]:
                entry["tool_calls"] = msg["tool_calls"]
            normalized.append(entry)
        return normalized

    async def check_health(self, target_model: str | None = None) -> tuple[bool, str | None, list[str]]:
        """
        Check if Ollama daemon is reachable and if target_model is present.
        Returns (is_available, error_message, list_of_installed_models).
        """
        model_name = target_model or self._default_model
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=_HEALTH_TIMEOUT) as client:
                res = await client.get("/api/tags")
                if res.status_code != 200:
                    return False, f"Ollama HTTP {res.status_code}", []
                data = res.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                # Check for exact or prefix match (e.g. qwen3:1.7b or qwen3:1.7b-instruct)
                found = any(
                    m == model_name or m.startswith(f"{model_name}:") or model_name.startswith(f"{m}:") or m.split(":")[0] == model_name.split(":")[0]
                    for m in models
                )
                if not found:
                    return False, f"Model '{model_name}' not found in Ollama. Available: {models}", models
                return True, None, models
        except httpx.ConnectError:
            return False, "Cannot connect to Ollama daemon on " + self._base_url, []
        except httpx.TimeoutException:
            return False, "Ollama health check timed out", []
        except Exception as e:
            return False, f"Ollama health check failed: {e}", []

    async def chat_stream(
        self,
        model_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stop: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat tokens from Ollama via POST /api/chat.
        """
        messages = messages or []
        model = model_id or self._default_model
        norm_messages = self.normalize_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": norm_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop
        if tools:
            payload["tools"] = tools

        client = self._get_client()
        start_time = time.monotonic()
        streamed_chunks = 0

        logger.info(
            "ollama_stream_request_start",
            model=model,
            num_messages=len(norm_messages),
        )

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code == 404:
                    raise LLMModelUnavailableError(f"Ollama model '{model}' not found.", status_code=404)
                if response.status_code >= 400:
                    err_body = await response.aread()
                    raise LLMError(f"Ollama error ({response.status_code}): {err_body.decode('utf-8', errors='ignore')}", status_code=response.status_code)

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk_json = json.loads(line)
                        msg = chunk_json.get("message", {})
                        content = msg.get("content", "") or msg.get("thinking", "") or chunk_json.get("response", "")
                        if content:
                            streamed_chunks += 1
                            yield content
                        if chunk_json.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("ollama_stream_complete", model=model, chunks=streamed_chunks, elapsed_ms=elapsed_ms)

        except httpx.TimeoutException as te:
            raise LLMTimeoutError(f"Ollama request for '{model}' timed out after {self._timeout}s") from te
        except (LLMError, LLMModelUnavailableError):
            raise
        except Exception as e:
            raise LLMError(f"Ollama inference error: {e}") from e

    async def chat_complete(
        self,
        model_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stop: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """
        Non-streaming chat completion from Ollama.
        """
        messages = messages or []
        model = model_id or self._default_model
        norm_messages = self.normalize_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": norm_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop
        if tools:
            payload["tools"] = tools

        client = self._get_client()
        start_time = time.monotonic()

        try:
            res = await client.post("/api/chat", json=payload)
            if res.status_code == 404:
                raise LLMModelUnavailableError(f"Ollama model '{model}' not found.", status_code=404)
            if res.status_code >= 400:
                raise LLMError(f"Ollama error ({res.status_code}): {res.text}", status_code=res.status_code)

            data = res.json()
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            msg = data.get("message", {})
            full_text = msg.get("content", "") or msg.get("thinking", "") or data.get("response", "")
            prompt_tokens = data.get("prompt_eval_count", max(1, len(str(messages).split()) * 2))
            eval_tokens = data.get("eval_count", max(1, len(full_text.split()) * 2))

            return GenerationResult(
                full_text=full_text,
                input_tokens=prompt_tokens,
                output_tokens=eval_tokens,
                model_id=model,
                latency_ms=elapsed_ms,
            )
        except httpx.TimeoutException as te:
            raise LLMTimeoutError(f"Ollama request for '{model}' timed out after {self._timeout}s") from te
        except (LLMError, LLMModelUnavailableError):
            raise
        except Exception as e:
            raise LLMError(f"Ollama inference error: {e}") from e

    async def embed(self, model_id: str | None = None, texts: list[str] | None = None) -> list[list[float]]:
        """
        Generate embeddings using Ollama /api/embed.
        """
        texts = texts or []
        model = model_id or self._default_model
        client = self._get_client()

        try:
            res = await client.post("/api/embed", json={"model": model, "input": texts})
            if res.status_code == 200:
                data = res.json()
                raw_emb = data.get("embeddings", [])
                return [list(map(float, e)) for e in raw_emb]
            # Fallback to single text /api/embeddings endpoint
            embeddings: list[list[float]] = []
            for text in texts:
                s_res = await client.post("/api/embeddings", json={"model": model, "prompt": text})
                if s_res.status_code == 200:
                    embeddings.append(s_res.json().get("embedding", []))
                else:
                    raise LLMError(f"Ollama embeddings error ({s_res.status_code}): {s_res.text}")
            return embeddings
        except Exception as e:
            raise LLMError(f"Ollama embedding error: {e}") from e
