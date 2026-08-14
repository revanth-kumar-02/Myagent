import os
import pytest
from pydantic import BaseModel, Field
from typing import List

from core.llm import (
    LLMProviderGateway, GroqProvider, RuleBasedLLMProvider,
    LLMProviderError, LLMTimeoutError, LLMRateLimitError
)
from core.planner import AgentPlanner, TaskPlan

class SimpleSchema(BaseModel):
    summary: str = Field(description="Summary text")
    items: List[str] = Field(default_factory=list)

@pytest.mark.asyncio
async def test_groq_gateway_detection():
    # Detects groq when key is provided
    gateway = LLMProviderGateway.get_provider(provider_type="groq", api_key="gsk_test_mock_key")
    assert isinstance(gateway, GroqProvider)
    assert gateway.api_key == "gsk_test_mock_key"
    assert gateway.model == "llama-3.3-70b-versatile"

@pytest.mark.asyncio
async def test_groq_missing_key_fallback():
    # Falls back to RuleBasedLLMProvider when key is 'none' or missing
    fallback = LLMProviderGateway.get_provider(provider_type="groq", api_key="none")
    assert isinstance(fallback, RuleBasedLLMProvider)
    text = await fallback.generate_text("Test fallback prompt")
    assert "RuleBasedLLM" in text

@pytest.mark.asyncio
async def test_groq_real_request_if_configured():
    # Live Groq test using real API key from environment
    key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not key or not key.startswith("gsk_"):
        pytest.skip("Groq API key not available for live network test")

    provider = GroqProvider(api_key=key, model="llama-3.3-70b-versatile")
    
    # 1. Text generation
    text = await provider.generate_text("Say hello in one word.")
    assert text is not None
    assert len(text) > 0

    # 2. Structured generation into Pydantic schema
    struct = await provider.generate_structured("List 2 primary colors", SimpleSchema)
    assert isinstance(struct, SimpleSchema)
    assert struct.summary is not None

@pytest.mark.asyncio
async def test_groq_malformed_response_handling():
    # Test handling of non-JSON response in generate_structured
    class MockBadGroq(GroqProvider):
        async def generate_text(self, prompt: str, system_prompt: str = None) -> str:
            return "This is not JSON text at all!"

    bad_provider = MockBadGroq(api_key="gsk_mock")
    with pytest.raises(LLMProviderError) as exc_info:
        await bad_provider.generate_structured("test", SimpleSchema)
    assert "Failed to parse structured response" in str(exc_info.value)

@pytest.mark.asyncio
async def test_groq_rate_limit_exception():
    class MockRateLimitGroq(GroqProvider):
        async def generate_text(self, prompt: str, system_prompt: str = None) -> str:
            raise LLMRateLimitError("Groq API rate limit exceeded")

    provider = MockRateLimitGroq(api_key="gsk_mock")
    with pytest.raises(LLMRateLimitError):
        await provider.generate_text("test")

@pytest.mark.asyncio
async def test_groq_planner_integration():
    planner = AgentPlanner()
    plan = await planner.generate_plan("Research FastAPI BackgroundTasks documentation")
    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) > 0
    assert plan.steps[0].tool in ["web_search", "browser_open", "browser", "filesystem", "search_files", "web_search_tavily", "web_search_brave"]
