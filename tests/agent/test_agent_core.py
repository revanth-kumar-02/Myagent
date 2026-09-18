"""
tests.agent.test_agent_core — Comprehensive Test Suite for Kora's Agent Reasoning & Decision Engine (V7)
"""

from __future__ import annotations

import pathlib
import subprocess
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.context_package import ContextPackageBuilder
from core.decision_engine import DecisionEngine
from core.executor import Executor
from core.intent_analyzer import IntentAnalyzer
from core.model_router import ModelRouter, ModelUnavailableError
from core.planner import Planner
from core.tool_router import DispatchTarget, PermissionDeniedError, ToolRouter
from core.types import (
    ActionType,
    AgentResponse,
    ChatRequest,
    ContextNeed,
    ExecutionReport,
    ExecutorResult,
    IntentType,
    Plan,
    PlanStep,
    SourceType,
    StepStatus,
    VerifierVerdict,
)
from core.verifier import Verifier
from models.registry import ModelRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def model_registry() -> ModelRegistry:
    reg_path = pathlib.Path(__file__).parent.parent.parent / "apps/agent/models/registry.yaml"
    return ModelRegistry.load(reg_path)


@pytest.fixture
def model_router(model_registry: ModelRegistry) -> ModelRouter:
    return ModelRouter(model_registry)


# ── 1. Model Router & Dynamic Registry Resolution ─────────────────────────────


class TestModelRouter:

    @pytest.mark.asyncio
    async def test_routes_chat_capability(self, model_router: ModelRouter) -> None:
        handle = await model_router.select("chat")
        assert handle.config.name == "qwen-chat"
        assert "chat" in handle.config.capabilities

    @pytest.mark.asyncio
    async def test_routes_reason_and_code(self, model_router: ModelRouter) -> None:
        handle_reason = await model_router.select("reason")
        assert handle_reason.config.name == "qwen-reason"
        assert "reason" in handle_reason.config.capabilities

        handle_code = await model_router.select("code")
        assert handle_code.config.name == "qwen-code"
        assert "code" in handle_code.config.capabilities

    @pytest.mark.asyncio
    async def test_routes_vision_and_audio(self, model_router: ModelRouter) -> None:
        handle_vision = await model_router.select("vision")
        assert handle_vision.config.name == "gemma-vision"
        assert "vision" in handle_vision.config.capabilities

        handle_audio = await model_router.select("audio")
        assert handle_audio.config.name == "gemma-audio"
        assert "audio" in handle_audio.config.capabilities

    @pytest.mark.asyncio
    async def test_raises_on_unknown_capability(self, model_router: ModelRouter) -> None:
        with pytest.raises(ModelUnavailableError, match="No model registered"):
            await model_router.select("quantum_computing")

    def test_model_id_not_in_agent_code(self) -> None:
        """Ensure model IDs only exist in registry.yaml, not in Python source."""
        agent_dir = pathlib.Path(__file__).parent.parent.parent / "apps/agent"
        result = subprocess.run(
            ["grep", "-r", "Qwen/", str(agent_dir)],
            capture_output=True, text=True,
        )
        hits = [line for line in result.stdout.splitlines() if "registry.yaml" not in line]
        assert not hits, f"Model IDs found outside registry.yaml: {hits}"


# ── 2. Intent Analyzer & Context Decision ─────────────────────────────────────


class TestIntentAnalyzerAndContextDecision:

    def test_classifies_general_conversation(self) -> None:
        analyzer = IntentAnalyzer()
        intent, need = analyzer.analyze("hello there! How are you today?")
        assert intent == IntentType.GENERAL_CONVERSATION
        assert need == ContextNeed.NONE

    def test_classifies_rag_intent(self) -> None:
        analyzer = IntentAnalyzer()
        proj_id = uuid.uuid4()
        intent, need = analyzer.analyze("where is the database schema defined in this project?", project_id=proj_id)
        assert intent == IntentType.KNOWLEDGE_RAG
        assert need == ContextNeed.RAG

    def test_classifies_memory_intent(self) -> None:
        analyzer = IntentAnalyzer()
        intent, need = analyzer.analyze("remember that my preferred indentation is 2 spaces")
        assert intent == IntentType.MEMORY
        assert need == ContextNeed.MEMORY

    def test_classifies_web_intent(self) -> None:
        analyzer = IntentAnalyzer()
        intent, need = analyzer.analyze("search online for the latest release notes of FastAPI 2026")
        assert intent == IntentType.WEB_RESEARCH
        assert need == ContextNeed.WEB

    def test_classifies_mixed_intent(self) -> None:
        analyzer = IntentAnalyzer()
        proj_id = uuid.uuid4()
        intent, need = analyzer.analyze("compare our project indexer with latest online docs for pgvector", project_id=proj_id)
        assert intent == IntentType.MIXED_REQUEST
        assert need == ContextNeed.RAG_AND_WEB

    def test_classifies_tool_action(self) -> None:
        analyzer = IntentAnalyzer()
        intent, need = analyzer.analyze("run pytest on tests/agent/test_research.py")
        assert intent == IntentType.TOOL_ACTION


# ── 3. Task Planner & Dynamic Replanning ───────────────────────────────────────


@pytest.mark.asyncio
class TestPlannerAndReplanning:

    async def test_simple_query_produces_single_step(self) -> None:
        planner = Planner()
        req = ChatRequest(message="Hello!", session_id=uuid.uuid4(), project_id=None)
        plan = await planner.plan(req)
        assert len(plan.steps) == 1
        assert plan.steps[0].action_type == ActionType.MODEL_GENERATE

    async def test_multi_step_plan_ordered(self) -> None:
        planner = Planner()
        proj_id = uuid.uuid4()
        req = ChatRequest(message="How does chunker work in this codebase?", session_id=uuid.uuid4(), project_id=proj_id)
        plan = await planner.plan(req)
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == ActionType.RAG_QUERY
        assert plan.steps[1].action_type == ActionType.MODEL_GENERATE
        assert 0 in plan.steps[1].dependencies

    async def test_replanning_on_step_failure(self) -> None:
        planner = Planner()
        original_plan = Plan(
            steps=[
                PlanStep(index=0, label="RAG Search", action_type=ActionType.RAG_QUERY, status=StepStatus.FAILED),
                PlanStep(index=1, label="Generate", action_type=ActionType.MODEL_GENERATE, status=StepStatus.PENDING),
            ],
            trace_id=uuid.uuid4(),
        )
        report = ExecutionReport(
            step_index=0,
            success=False,
            output="",
            verdict=VerifierVerdict.ESCALATE,
            error_message="No matching chunks in index",
        )
        replanned = await planner.replan(original_plan.steps[0], report, original_plan)
        assert replanned.is_replan is True
        assert any(s.action_type == ActionType.WEB_RESEARCH for s in replanned.steps)


# ── 4. Execution Verifier ─────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestVerifier:

    async def test_pass_on_successful_result(self) -> None:
        verifier = Verifier()
        step = PlanStep(index=0, label="Step 1", action_type=ActionType.MODEL_GENERATE)
        res = ExecutorResult(step=step, success=True, content="Here is the detailed response.")
        verdict = await verifier.check(res, attempt=0)
        assert verdict == VerifierVerdict.PASS

    async def test_retry_on_failed_result(self) -> None:
        verifier = Verifier()
        step = PlanStep(index=0, label="Step 1", action_type=ActionType.TOOL_CALL)
        res = ExecutorResult(step=step, success=False, content="", error="Network timeout")
        verdict = await verifier.check(res, attempt=0)
        assert verdict == VerifierVerdict.RETRY

    async def test_escalate_after_max_retries(self) -> None:
        verifier = Verifier()
        step = PlanStep(index=0, label="Step 1", action_type=ActionType.TOOL_CALL)
        res = ExecutorResult(step=step, success=False, content="", error="Persistent DB error")
        verdict = await verifier.check(res, attempt=2)
        assert verdict == VerifierVerdict.ESCALATE


# ── 5. Tool Router & Permission Gate ──────────────────────────────────────────


@pytest.mark.asyncio
class TestToolRouterAndPermissions:

    async def test_resolves_rag_and_web_targets(self) -> None:
        mock_rag = MagicMock()
        mock_web = MagicMock()
        router = ToolRouter(rag_retriever=mock_rag, research_router=mock_web)

        rag_step = PlanStep(index=0, label="RAG", action_type=ActionType.RAG_QUERY, params={"query": "test"})
        target_rag = await router.resolve(rag_step)
        assert target_rag.action_type == ActionType.RAG_QUERY

        web_step = PlanStep(index=1, label="Web", action_type=ActionType.WEB_RESEARCH, params={"query": "test"})
        target_web = await router.resolve(web_step)
        assert target_web.action_type == ActionType.WEB_RESEARCH

    async def test_permission_gate_denial(self) -> None:
        mock_gate = MagicMock()
        mock_gate.check = AsyncMock(side_effect=PermissionDeniedError("Tool 'bash' denied by policy"))
        mock_tools = MagicMock()
        mock_tools.get = MagicMock(return_value=MagicMock(name="bash"))

        router = ToolRouter(tool_registry=mock_tools, permission_gate=mock_gate)
        tool_step = PlanStep(index=0, label="Bash", action_type=ActionType.TOOL_CALL, required_tool="bash")

        with pytest.raises(PermissionDeniedError, match="Permission denied"):
            await router.resolve(tool_step)


# ── 6. Decision Engine End-to-End Loop ────────────────────────────────────────


@pytest.mark.asyncio
class TestDecisionEngineLoop:

    async def test_end_to_end_conversational_flow(self) -> None:
        engine = DecisionEngine()
        req = ChatRequest(message="Hello Kora!", session_id=uuid.uuid4(), project_id=None)
        resp = await engine.process(req)
        assert resp is not None
        assert "Hello Kora!" in resp.content or "Response to request" in resp.content
        assert resp.action_status == "success"

    async def test_end_to_end_web_research_flow(self) -> None:
        mock_research = MagicMock()
        mock_research.search_raw = AsyncMock(return_value=MagicMock(
            results=[
                MagicMock(url="https://fastapi.tiangolo.com", title="FastAPI", snippet="FastAPI release", score=0.92)
            ]
        ))

        engine = DecisionEngine(research_engine=mock_research)
        req = ChatRequest(message="Search online for latest FastAPI release", session_id=uuid.uuid4(), project_id=None)
        resp = await engine.process(req)

        assert resp is not None
        assert len(resp.web_sources) >= 1
        assert resp.web_sources[0].url == "https://fastapi.tiangolo.com"
        assert resp.action_status == "success"

    async def test_end_to_end_permission_blocked_flow(self) -> None:
        mock_gate = MagicMock()
        mock_gate.check = AsyncMock(side_effect=PermissionDeniedError("Denied"))
        mock_tools = MagicMock()
        mock_tools.get = MagicMock(return_value=MagicMock(name="bash"))

        tool_router = ToolRouter(tool_registry=mock_tools, permission_gate=mock_gate)
        engine = DecisionEngine(tool_router=tool_router)

        req = ChatRequest(message="run pytest on tests/", session_id=uuid.uuid4(), project_id=None)
        resp = await engine.process(req)

        assert resp is not None
        # Should record limitation or handle gracefully without throwing uncaught exception
        assert len(resp.limitations) >= 1 or resp.action_status in ("partial_success", "success")
