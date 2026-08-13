import pytest
from core.llm import LLMProviderGateway, RuleBasedLLMProvider
from core.planner import AgentPlanner, TaskPlan
from core.tools.registry import tool_registry, ToolResult
from core.verifier import AgentVerifier
from core.agent import AgentOrchestrator
from db.session import init_db

@pytest.mark.asyncio
async def test_llm_provider_gateway_fallback():
    provider = LLMProviderGateway.get_provider(provider_type="groq", api_key="none")
    assert isinstance(provider, RuleBasedLLMProvider)
    text = await provider.generate_text("Hello agent")
    assert "RuleBasedLLM" in text

@pytest.mark.asyncio
async def test_agent_planner_generation():
    planner = AgentPlanner()
    plan = await planner.generate_plan("Research best vector databases")
    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) > 0
    assert plan.steps[0].tool in ["web_search", "filesystem", "browser", "scheduler"]

@pytest.mark.asyncio
async def test_tool_registry_execution():
    res = await tool_registry.execute_tool("web_search", {"query": "FastAPI testing"})
    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "query" in res.data

@pytest.mark.asyncio
async def test_agent_verifier():
    verifier = AgentVerifier()
    v_res = await verifier.verify_step("Build backend API", "Create database models", {"status": "ok"})
    assert v_res.success is True

@pytest.mark.asyncio
async def test_agent_orchestrator_execution():
    await init_db()
    orchestrator = AgentOrchestrator()
    task = await orchestrator.run_goal("Test end to end goal execution")
    assert task.status in ["completed", "executing", "planning"]
    assert task.id is not None
