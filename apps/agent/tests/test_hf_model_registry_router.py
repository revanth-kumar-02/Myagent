import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel, Field

from core.llm.registry import (
    ModelRole,
    ModelProfile,
    ModelConfig,
    ModelRegistry,
    model_registry
)
from core.llm.router import ModelRouter, model_router
from core.llm.gateway import LLMProviderGateway, llm_gateway
from core.llm.providers.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMAuthenticationError,
    LLMInvalidModelError,
    LLMUnsupportedTaskError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInferenceError
)
from core.llm.providers.huggingface import HuggingFaceProvider
from core.llm.providers.rule_based import RuleBasedLLMProvider
from core.planner import AgentPlanner, TaskPlan
from core.verifier import AgentVerifier, VerificationResult

class SampleSchema(BaseModel):
    summary: str
    score: int
    tags: list[str] = Field(default_factory=list)

# ─── 1. Registry Loading & Role Resolution Tests ───────────────────────────────

def test_registry_loading_all_required_roles():
    """Verify registry initializes with all 6 required roles."""
    registry = ModelRegistry()
    roles = registry.list_roles()
    expected_roles = [
        ModelRole.CHAT.value,
        ModelRole.REASONING.value,
        ModelRole.CODING.value,
        ModelRole.VISION.value,
        ModelRole.SPEECH_TO_TEXT.value,
        ModelRole.TEXT_TO_SPEECH.value
    ]
    for r in expected_roles:
        assert r in roles, f"Missing required role: {r}"
        cfg = registry.get_model_config(r)
        assert cfg is not None
        assert cfg.enabled is True
        assert cfg.provider == "huggingface"
        assert len(cfg.model_id) > 0

def test_registry_configuration_driven_overrides(monkeypatch):
    """Verify model IDs are configuration-driven via environment variables."""
    monkeypatch.setenv("HF_CHAT_MODEL", "custom-org/custom-chat-model")
    monkeypatch.setenv("HF_REASONING_MODEL", "custom-org/custom-reasoning-model")
    monkeypatch.setenv("HF_CODING_MODEL", "custom-org/custom-coding-model")
    monkeypatch.setenv("HF_VISION_MODEL", "custom-org/custom-vision-model")
    monkeypatch.setenv("HF_STT_MODEL", "custom-org/custom-stt-model")
    monkeypatch.setenv("HF_TTS_MODEL", "custom-org/custom-tts-model")

    registry = ModelRegistry()
    assert registry.get_model_config("chat").model_id == "custom-org/custom-chat-model"
    assert registry.get_model_config("reasoning").model_id == "custom-org/custom-reasoning-model"
    assert registry.get_model_config("coding").model_id == "custom-org/custom-coding-model"
    assert registry.get_model_config("vision").model_id == "custom-org/custom-vision-model"
    assert registry.get_model_config("speech_to_text").model_id == "custom-org/custom-stt-model"
    assert registry.get_model_config("text_to_speech").model_id == "custom-org/custom-tts-model"

def test_registry_capability_and_task_validation():
    """Verify capability and task compatibility validation."""
    registry = ModelRegistry()
    chat_cfg = registry.get_model_config(ModelRole.CHAT)
    assert registry.validate_capability(chat_cfg, "chat") is True
    assert registry.validate_capability(chat_cfg, "nonexistent_capability") is False
    assert registry.validate_task_compatibility(chat_cfg, "text-generation") is True
    assert registry.validate_task_compatibility(chat_cfg, "automatic-speech-recognition") is False

def test_registry_future_multi_model_slots():
    """Verify registry supports primary, fallback, fast, deep profiles without Core changes."""
    registry = ModelRegistry()
    # Register a fallback model for reasoning
    fallback_cfg = ModelConfig(
        model_id="Qwen/Qwen2.5-14B-Instruct",
        role=ModelRole.REASONING,
        profile=ModelProfile.FALLBACK.value,
        task="text-generation"
    )
    registry.register_model(fallback_cfg)

    # Primary and fallback should both be retrievable
    primary = registry.get_model_config("reasoning", profile="primary")
    fallback = registry.get_model_config("reasoning", profile="fallback")

    assert primary.model_id != fallback.model_id
    assert fallback.model_id == "Qwen/Qwen2.5-14B-Instruct"

# ─── 2. Model Router Tests ────────────────────────────────────────────────────

def test_model_router_role_resolution():
    """Verify ModelRouter resolves functional roles to model configs."""
    router = ModelRouter()
    chat_model = router.get_model("chat")
    assert chat_model.role == ModelRole.CHAT

    reasoning_model = router.get_model("reasoning")
    assert reasoning_model.role == ModelRole.REASONING

    coding_model = router.get_model("coding")
    assert coding_model.role == ModelRole.CODING

    vision_model = router.get_model("vision")
    assert vision_model.role == ModelRole.VISION

def test_model_router_invalid_role_handling():
    """Verify router raises LLMInvalidModelError for unconfigured roles."""
    router = ModelRouter()
    with pytest.raises(LLMInvalidModelError):
        router.get_model("nonexistent_unknown_role")

def test_model_router_graceful_fallback_without_token():
    """Verify router gracefully provides RuleBased fallback when HF_TOKEN is absent."""
    hf_no_token = HuggingFaceProvider(token=None)
    router = ModelRouter(hf_provider=hf_no_token)
    provider = router.get_provider("reasoning")
    assert isinstance(provider, RuleBasedLLMProvider)

# ─── 3. Hugging Face Provider Security & Error Handling Tests ─────────────────

def test_hf_provider_token_security_and_masking():
    """Verify HF token is never logged or exposed in plain text."""
    secret_token = "hf_secretTokenXYZ1234567890"
    provider = HuggingFaceProvider(token=secret_token)
    masked = provider._mask_token()
    assert secret_token not in masked
    assert masked == "hf_s****7890"

def test_hf_provider_missing_token_raises_auth_error():
    """Verify missing token raises LLMAuthenticationError."""
    provider = HuggingFaceProvider(token="")
    with pytest.raises(LLMAuthenticationError):
        provider._get_headers()

@pytest.mark.asyncio
async def test_hf_provider_task_mismatch_raises_error():
    """Verify task mismatch raises LLMUnsupportedTaskError."""
    provider = HuggingFaceProvider(token="hf_mock_token")
    text_config = ModelConfig(
        model_id="meta-llama/Llama-3.3-70B-Instruct",
        role=ModelRole.CHAT,
        task="text-generation"
    )
    # Attempting to transcribe audio with a text-generation model must raise error
    with pytest.raises(LLMUnsupportedTaskError):
        await provider.transcribe_audio(b"audio_bytes", model_config=text_config)

@pytest.mark.asyncio
async def test_hf_provider_structured_json_parsing():
    """Verify Hugging Face structured JSON response extraction and Pydantic validation."""
    provider = HuggingFaceProvider(token="hf_mock_token")

    mock_json_reply = '```json\n{"summary": "Test Summary", "score": 98, "tags": ["hf", "router"]}\n```'
    with patch.object(provider, "generate_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_json_reply
        result = await provider.generate_structured("Analyze this", SampleSchema)
        assert isinstance(result, SampleSchema)
        assert result.summary == "Test Summary"
        assert result.score == 98
        assert "hf" in result.tags

# ─── 4. LLM Gateway & Role-Based Workload Selection Tests ──────────────────────

@pytest.mark.asyncio
async def test_llm_gateway_text_and_structured_generation():
    """Verify LLMProviderGateway routes to the correct role models."""
    gateway = LLMProviderGateway()

    # RuleBased fallback active (no network calls)
    text_res = await gateway.generate_text("Hello Cocoa", role=ModelRole.CHAT)
    assert "RuleBasedLLM" in text_res

    struct_res = await gateway.generate_structured("Plan goal", SampleSchema, role=ModelRole.REASONING)
    assert isinstance(struct_res, SampleSchema)

@pytest.mark.asyncio
async def test_llm_gateway_multimodal_vision_and_audio():
    """Verify LLMProviderGateway handles multimodal vision, STT, and TTS methods."""
    gateway = LLMProviderGateway()

    vision_res = await gateway.understand_vision(b"dummy_image", "What is in this image?", role=ModelRole.VISION)
    assert "RuleBased vision" in vision_res

    stt_res = await gateway.transcribe_audio(b"dummy_audio", role=ModelRole.SPEECH_TO_TEXT)
    assert "RuleBased transcribed" in stt_res

    tts_res = await gateway.synthesize_speech("Hello Rev", role=ModelRole.TEXT_TO_SPEECH)
    assert isinstance(tts_res, bytes)

# ─── 5. Existing Agent Components Integration Tests ───────────────────────────

@pytest.mark.asyncio
async def test_planner_uses_reasoning_role_via_gateway():
    """Verify AgentPlanner generates valid structured plans via the gateway."""
    planner = AgentPlanner()
    goal = "Create a new authentication endpoint"
    plan = await planner.generate_plan(goal)
    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) > 0

@pytest.mark.asyncio
async def test_verifier_uses_reasoning_role_via_gateway():
    """Verify AgentVerifier validates step completion via the gateway."""
    verifier = AgentVerifier()
    goal = "Check git branch status"
    step_title = "Inspect repository Git status"
    res = await verifier.verify_step(goal, step_title, {"status": "clean", "exit_code": 0})
    assert isinstance(res, VerificationResult)
    assert res.success is True

def test_no_legacy_hardcoded_model_ids_in_planner_or_verifier():
    """Verify Agent Core classes do not have hardcoded legacy Groq or external model IDs."""
    planner = AgentPlanner()
    verifier = AgentVerifier()
    assert not hasattr(planner, "groq_model")
    assert not hasattr(verifier, "groq_model")
