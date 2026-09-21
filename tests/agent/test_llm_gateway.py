"""
tests.agent.test_llm_gateway — Unit and integration tests for Hugging Face LLM Gateway (V24)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from models.providers.huggingface import (
    HuggingFaceProvider,
    LLMAuthError,
    LLMError,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from models.registry import ModelRegistry
from models.types import ModelConfig, ModelHandle


@pytest.mark.asyncio
async def test_request_normalization() -> None:
    raw_messages = [
        {"role": "SYSTEM", "content": "You are Kora."},
        {"role": "USER", "content": "Hello world"},
        {"role": "unknown_role", "content": "Fallback to user"},
    ]
    norm = HuggingFaceProvider.normalize_messages(raw_messages)
    assert len(norm) == 3
    assert norm[0] == {"role": "system", "content": "You are Kora."}
    assert norm[1] == {"role": "user", "content": "Hello world"}
    assert norm[2] == {"role": "user", "content": "Fallback to user"}


@pytest.mark.asyncio
async def test_chat_stream_success() -> None:
    sse_data = (
        'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": " from"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": " Qwen!"}}]}\n\n'
        'data: [DONE]\n\n'
    )

    class MockStreamContext:
        def __init__(self, status_code: int = 200) -> None:
            self.status_code = status_code

        async def __aenter__(self) -> "MockStreamContext":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def aiter_lines(self):
            for line in sse_data.split("\n"):
                yield line

        async def aread(self) -> bytes:
            return b""

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.stream.return_value = MockStreamContext(200)

    provider = HuggingFaceProvider(api_token="hf_test_token", client=mock_client)
    chunks = []
    async for chunk in provider.chat_stream(
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        messages=[{"role": "user", "content": "Hi"}],
    ):
        chunks.append(chunk)

    assert chunks == ["Hello", " from", " Qwen!"]
    assert "".join(chunks) == "Hello from Qwen!"


@pytest.mark.asyncio
async def test_chat_complete_success() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Generated completion text"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8},
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.post.return_value = mock_response

    provider = HuggingFaceProvider(api_token="hf_test_token", client=mock_client)
    result = await provider.chat_complete(
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        messages=[{"role": "user", "content": "Generate answer"}],
    )

    assert result.full_text == "Generated completion text"
    assert result.input_tokens == 10
    assert result.output_tokens == 8
    assert result.model_id == "Qwen/Qwen3-4B-Instruct-2507"


@pytest.mark.asyncio
async def test_auth_error_handling() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.post.return_value = mock_response

    provider = HuggingFaceProvider(api_token="invalid_token", client=mock_client)
    with pytest.raises(LLMAuthError) as exc_info:
        await provider.chat_complete(
            model_id="Qwen/Qwen3-4B-Instruct-2507",
            messages=[{"role": "user", "content": "Test"}],
        )

    assert exc_info.value.status_code == 401
    # Verify no token is present in error representation
    assert "invalid_token" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_model_unavailable_error() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.text = "Model is currently loading"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.post.return_value = mock_response

    provider = HuggingFaceProvider(api_token="test_token", client=mock_client)
    with patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(LLMModelUnavailableError) as exc_info:
            await provider.chat_complete(
                model_id="google/gemma-4-E4B-it",
                messages=[{"role": "user", "content": "Test"}],
            )
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_embedding_generation() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = [
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6, 0.7, 0.8],
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.post.return_value = mock_response

    provider = HuggingFaceProvider(api_token="test_token", client=mock_client)
    vectors = await provider.embed(
        model_id="BAAI/bge-m3",
        texts=["first text", "second text"],
    )

    assert len(vectors) == 2
    assert vectors[0] == [0.1, 0.2, 0.3, 0.4]
    assert vectors[1] == [0.5, 0.6, 0.7, 0.8]


@pytest.mark.asyncio
async def test_model_handle_delegation() -> None:
    mock_provider = AsyncMock()
    mock_provider.chat_complete.return_value = MagicMock(
        full_text="Delegated response",
        input_tokens=5,
        output_tokens=3,
        model_id="Qwen/Qwen3-4B-Instruct-2507",
    )

    config = ModelConfig(
        name="qwen-chat",
        provider="huggingface",
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        capabilities=["chat"],
        context_window=32768,
    )

    handle = ModelHandle(config=config, provider=mock_provider)
    res = await handle.generate([{"role": "user", "content": "Hello"}])
    assert res.full_text == "Delegated response"
    mock_provider.chat_complete.assert_called_once()
