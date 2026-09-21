"""
models.providers.huggingface — Hugging Face LLM Gateway Provider

Responsibilities:
  - Communicate with the Hugging Face Inference API / Router
  - Support: OpenAI-compatible chat completion (streaming and non-streaming), text embeddings
  - Handle rate limiting, retries with exponential backoff, timeout, and cancellation
  - Provide structured exception classes
  - Track usage metadata (tokens, latency)
  - Strict token safety: never expose or log API tokens
  - Never expose model IDs to callers — always receive them from ModelRegistry
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import httpx
import structlog

from config import settings
from models.types import GenerationResult

logger = structlog.get_logger(__name__)

_DEFAULT_BASE_URL = "https://router.huggingface.co/v1"
_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 1
_BASE_BACKOFF = 0.5


class LLMError(Exception):
    """Base exception for all LLM Gateway errors."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class LLMTimeoutError(LLMError):
    """Raised when an inference request times out."""


class LLMRateLimitError(LLMError):
    """Raised when rate limits or quotas are exceeded (HTTP 429)."""


class LLMAuthError(LLMError):
    """Raised when API token is invalid or missing (HTTP 401/403)."""


class LLMModelUnavailableError(LLMError):
    """Raised when the requested model is not found, disabled, or loading (HTTP 503)."""


class HuggingFaceProvider:
    """
    Production-grade Hugging Face Inference Provider & LLM Gateway.
    Connects Agent Core and Model Router to hosted Hugging Face models.
    """

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = api_token or settings.huggingface_api_token
        self._base_url = (base_url or settings.huggingface_base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "Content-Type": "application/json",
            }
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    @staticmethod
    def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Normalize message list to standard role/content dictionaries."""
        normalized: list[dict[str, str]] = []
        for msg in messages:
            role = str(msg.get("role", "user")).lower()
            if role not in ("system", "user", "assistant"):
                role = "user"
            content = str(msg.get("content", ""))
            normalized.append({"role": role, "content": content})
        return normalized

    def _get_chat_url(self, model_id: str) -> str:
        """Resolve the chat completions endpoint path based on base_url structure."""
        if self._base_url.endswith("/v1"):
            return "/chat/completions"
        elif "api-inference" in self._base_url:
            return f"/models/{model_id}/v1/chat/completions"
        else:
            return "/v1/chat/completions"

    async def chat_stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion token deltas from Hugging Face via SSE with diagnostics.
        """
        norm_messages = self.normalize_messages(messages)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": norm_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop

        url = self._get_chat_url(model_id)
        client = self._get_client()

        logger.info(
            "llm_request_start",
            selected_model=model_id,
            endpoint=url,
            streaming=True,
            num_messages=len(norm_messages),
        )

        attempt = 0
        while True:
            start_time = time.monotonic()
            try:
                streamed_tokens = 0
                async with client.stream("POST", url, json=payload) as response:
                    logger.info(
                        "llm_http_response",
                        selected_model=model_id,
                        http_status=response.status_code,
                    )

                    if response.status_code in (401, 403):
                        logger.error("llm_auth_error", selected_model=model_id, http_status=response.status_code)
                        raise LLMAuthError("Invalid or missing Hugging Face API token", status_code=response.status_code)
                    if response.status_code == 429:
                        if attempt < _MAX_RETRIES:
                            attempt += 1
                            backoff = _BASE_BACKOFF * (2 ** (attempt - 1))
                            logger.warning("llm_rate_limit_retry", selected_model=model_id, attempt=attempt, backoff=backoff)
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("llm_rate_limit_exceeded", selected_model=model_id)
                        raise LLMRateLimitError("Hugging Face API rate limit exceeded", status_code=429)
                    if response.status_code == 503:
                        if attempt < _MAX_RETRIES:
                            attempt += 1
                            backoff = _BASE_BACKOFF * (2 ** (attempt - 1))
                            logger.info("llm_model_loading_retry", selected_model=model_id, attempt=attempt, backoff=backoff)
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("llm_model_unavailable", selected_model=model_id, http_status=503)
                        raise LLMModelUnavailableError(f"Model {model_id} currently unavailable / loading", status_code=503)

                    if response.status_code >= 400:
                        error_body = await response.aread()
                        err_str = error_body.decode("utf-8", errors="ignore")
                        logger.error("llm_api_error", selected_model=model_id, http_status=response.status_code, error=err_str)
                        raise LLMError(f"HF API error ({response.status_code}): {err_str}", status_code=response.status_code)

                    logger.info("llm_streaming_start", selected_model=model_id)

                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        streamed_tokens += 1
                                        yield content
                            except json.JSONDecodeError:
                                continue

                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "llm_streaming_completion",
                    selected_model=model_id,
                    streamed_chunks=streamed_tokens,
                    latency_ms=elapsed_ms,
                )
                logger.info("llm_request_completion", selected_model=model_id, status="success", latency_ms=elapsed_ms)
                return

            except httpx.TimeoutException as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.warning("llm_timeout", selected_model=model_id, attempt=attempt, elapsed_ms=elapsed_ms)
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMTimeoutError(f"Request to model {model_id} timed out after {self._timeout}s") from te
            except (LLMAuthError, LLMRateLimitError, LLMModelUnavailableError, LLMError):
                raise
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("llm_exception", selected_model=model_id, attempt=attempt, error=str(exc), elapsed_ms=elapsed_ms)
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMError(f"Inference error with model {model_id}: {exc}") from exc

    async def chat_complete(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stop: list[str] | None = None,
    ) -> GenerationResult:
        """
        Non-streaming chat completion with detailed diagnostics.
        """
        norm_messages = self.normalize_messages(messages)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": norm_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop

        url = self._get_chat_url(model_id)
        client = self._get_client()

        logger.info(
            "llm_request_start",
            selected_model=model_id,
            endpoint=url,
            streaming=False,
            num_messages=len(norm_messages),
        )

        attempt = 0
        while True:
            start_time = time.monotonic()
            try:
                resp = await client.post(url, json=payload)
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                logger.info(
                    "llm_http_response",
                    selected_model=model_id,
                    http_status=resp.status_code,
                    latency_ms=elapsed_ms,
                )

                if resp.status_code in (401, 403):
                    logger.error("llm_auth_error", selected_model=model_id, http_status=resp.status_code)
                    raise LLMAuthError("Invalid or missing Hugging Face API token", status_code=resp.status_code)
                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        attempt += 1
                        backoff = _BASE_BACKOFF * (2 ** (attempt - 1))
                        logger.warning("llm_rate_limit_retry", selected_model=model_id, attempt=attempt, backoff=backoff)
                        await asyncio.sleep(backoff)
                        continue
                    logger.error("llm_rate_limit_exceeded", selected_model=model_id)
                    raise LLMRateLimitError("Hugging Face API rate limit exceeded", status_code=429)
                if resp.status_code == 503:
                    if attempt < _MAX_RETRIES:
                        attempt += 1
                        backoff = _BASE_BACKOFF * (2 ** (attempt - 1))
                        logger.info("llm_model_loading_retry", selected_model=model_id, attempt=attempt, backoff=backoff)
                        await asyncio.sleep(backoff)
                        continue
                    logger.error("llm_model_unavailable", selected_model=model_id, http_status=503)
                    raise LLMModelUnavailableError(f"Model {model_id} currently unavailable", status_code=503)

                if resp.status_code >= 400:
                    logger.error("llm_api_error", selected_model=model_id, http_status=resp.status_code, error=resp.text)
                    raise LLMError(f"HF API error ({resp.status_code}): {resp.text}", status_code=resp.status_code)

                data = resp.json()
                choices = data.get("choices", [])
                full_text = ""
                if choices:
                    full_text = choices[0].get("message", {}).get("content", "")

                usage = data.get("usage", {})
                in_tokens = usage.get("prompt_tokens", len(json.dumps(norm_messages)) // 4)
                out_tokens = usage.get("completion_tokens", len(full_text) // 4)

                logger.info(
                    "llm_request_completion",
                    selected_model=model_id,
                    status="success",
                    in_tokens=in_tokens,
                    out_tokens=out_tokens,
                    latency_ms=elapsed_ms,
                )

                return GenerationResult(
                    full_text=full_text,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    model_id=model_id,
                    latency_ms=elapsed_ms,
                )

            except httpx.TimeoutException as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.warning("llm_timeout", selected_model=model_id, attempt=attempt, elapsed_ms=elapsed_ms)
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMTimeoutError(f"Request to model {model_id} timed out after {self._timeout}s") from te
            except (LLMAuthError, LLMRateLimitError, LLMModelUnavailableError, LLMError):
                raise
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("llm_exception", selected_model=model_id, attempt=attempt, error=str(exc), elapsed_ms=elapsed_ms)
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMError(f"Inference error with model {model_id}: {exc}") from exc

    async def embed(
        self,
        model_id: str,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate dense embeddings for a list of texts using Hugging Face router / endpoint.
        """
        if not texts:
            return []

        # Try OpenAI-compatible /embeddings if base_url is router /v1
        if self._base_url.endswith("/v1"):
            url = "/embeddings"
            body = {"model": model_id, "input": texts}
        else:
            url = f"/pipeline/feature-extraction/{model_id}"
            body = {"inputs": texts, "options": {"wait_for_model": True}}

        client = self._get_client()

        attempt = 0
        while True:
            try:
                resp = await client.post(url, json=body)
                if resp.status_code in (401, 403):
                    raise LLMAuthError("Invalid or missing Hugging Face API token", status_code=resp.status_code)
                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        attempt += 1
                        await asyncio.sleep(_BASE_BACKOFF * (2 ** (attempt - 1)))
                        continue
                    raise LLMRateLimitError("Hugging Face API rate limit exceeded", status_code=429)
                if resp.status_code >= 400:
                    raise LLMError(f"Embedding error ({resp.status_code}): {resp.text}", status_code=resp.status_code)

                raw = resp.json()
                # If OpenAI-compatible format
                if isinstance(raw, dict) and "data" in raw:
                    return [item["embedding"] for item in raw["data"]]
                if isinstance(raw, list) and raw and isinstance(raw[0], (int, float)):
                    return [raw]
                if isinstance(raw, list) and raw and isinstance(raw[0], list):
                    if isinstance(raw[0][0], (int, float)):
                        return raw
                    pooled: list[list[float]] = []
                    for item in raw:
                        if isinstance(item, list) and item and isinstance(item[0], list):
                            dim = len(item[0])
                            avg = [sum(tok[d] for tok in item) / len(item) for d in range(dim)]
                            pooled.append(avg)
                        else:
                            pooled.append(item)
                    return pooled
                return []

            except httpx.TimeoutException as te:
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMTimeoutError(f"Embedding request for {model_id} timed out") from te
            except (LLMAuthError, LLMRateLimitError, LLMError):
                raise
            except Exception as exc:
                if attempt < _MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_BASE_BACKOFF * attempt)
                    continue
                raise LLMError(f"Embedding error for model {model_id}: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
