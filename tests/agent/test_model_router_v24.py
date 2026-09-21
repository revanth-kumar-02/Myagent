"""
tests.agent.test_model_router_v24 — Tests for Model Registry and Router (V24)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from config import settings
from core.model_router import ModelRouter, ModelUnavailableError
from models.registry import ModelRegistry


def test_registry_loads_v24_models() -> None:
    registry = ModelRegistry.load(settings.model_registry_path)
    models = {m.name: m for m in registry.all()}

    # Verify model names
    assert "qwen-chat" in models
    assert "qwen-reason" in models
    assert "qwen-code" in models
    assert "gemma-vision" in models
    assert "gemma-audio" in models
    assert "embed-model" in models

    # Verify model IDs from registry
    assert models["qwen-chat"].model_id == "Qwen/Qwen3-4B-Instruct-2507"
    assert models["qwen-reason"].model_id == "Qwen/Qwen3-30B-A3B-Instruct-2507"
    assert models["qwen-code"].model_id == "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    assert models["gemma-vision"].model_id == "google/gemma-4-E4B-it"
    assert models["gemma-audio"].model_id == "google/gemma-4-E4B-it"
    assert models["embed-model"].model_id == "BAAI/bge-m3"


@pytest.mark.asyncio
async def test_capability_routing() -> None:
    registry = ModelRegistry.load(settings.model_registry_path)
    mock_provider = AsyncMock()
    router = ModelRouter(registry=registry, default_provider=mock_provider)

    chat_handle = await router.select("chat")
    assert chat_handle.config.name == "qwen-chat"
    assert chat_handle.config.model_id == "Qwen/Qwen3-4B-Instruct-2507"

    reason_handle = await router.select("reason")
    assert reason_handle.config.name == "qwen-reason"
    assert reason_handle.config.model_id == "Qwen/Qwen3-30B-A3B-Instruct-2507"

    code_handle = await router.select("code")
    assert code_handle.config.name == "qwen-code"
    assert code_handle.config.model_id == "Qwen/Qwen3-Coder-30B-A3B-Instruct"

    vision_handle = await router.select("vision")
    assert vision_handle.config.name == "gemma-vision"
    assert vision_handle.config.model_id == "google/gemma-4-E4B-it"

    audio_handle = await router.select("audio")
    assert audio_handle.config.name == "gemma-audio"
    assert audio_handle.config.model_id == "google/gemma-4-E4B-it"

    embed_handle = await router.select_embedding()
    assert embed_handle.config.name == "embed-model"
    assert embed_handle.config.model_id == "BAAI/bge-m3"


@pytest.mark.asyncio
async def test_unknown_capability_raises() -> None:
    registry = ModelRegistry.load(settings.model_registry_path)
    router = ModelRouter(registry=registry)
    with pytest.raises(ModelUnavailableError):
        await router.select("non_existent_capability")
