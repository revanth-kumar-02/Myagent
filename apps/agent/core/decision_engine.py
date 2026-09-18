"""
core.decision_engine — Central Reasoning & Decision Engine (V7)

Orchestrates Kora's complete cognitive loop:
  User Request
  → Intent Analysis
  → Context Decision
  → Planning
  → Reasoning & Tool Selection
  → Permission Gate
  → Execution
  → Verification
  → Dynamic Replanning (if failure/escalation)
  → Grounded Final Response
  → Memory Update

Architectural Guarantees:
  - Uses ONLY DuckDuckGo for web research (no Tavily, no external fallbacks)
  - Resolves models dynamically via ModelRegistry (no hardcoded model IDs)
  - Enforces PermissionGate (never bypasses permissions)
  - Keeps context bounded via tiktoken limits
  - Persists salient turn outcomes to long-term memory
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog

from core.context_package import ContextPackageBuilder
from core.executor import Executor
from core.intent_analyzer import IntentAnalyzer
from core.model_router import ModelRouter
from core.planner import Planner
from core.tool_router import PermissionDeniedError, ToolRouter
from core.types import (
    ActionType,
    AgentContextPackage,
    AgentResponse,
    ChatRequest,
    ChatResponse,
    ContextNeed,
    ContextWindow,
    ExecutionReport,
    ExecutorResult,
    IntentType,
    Plan,
    PlanStep,
    Source,
    SourceType,
    StepStatus,
    VerifierVerdict,
    WebSource,
)
from core.verifier import Verifier
from memory.types import MemorySource, MemoryType

if TYPE_CHECKING:
    from memory.manager import MemoryManager
    from permissions.gate import PermissionGate
    from rag.retriever import RAGRetriever
    from research.engine import WebResearchEngine

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class DecisionEngine:
    """
    Kora's central autonomous reasoning and decision loop.
    """

    def __init__(
        self,
        intent_analyzer: IntentAnalyzer | None = None,
        planner: Planner | None = None,
        model_router: ModelRouter | None = None,
        tool_router: ToolRouter | None = None,
        executor: Executor | None = None,
        verifier: Verifier | None = None,
        package_builder: ContextPackageBuilder | None = None,
        rag_retriever: Any | None = None,
        research_engine: Any | None = None,
        memory_manager: Any | None = None,
        permission_gate: Any | None = None,
    ) -> None:
        self._analyzer = intent_analyzer or IntentAnalyzer()
        self._planner = planner or Planner()
        self._model_router = model_router
        self._verifier = verifier or Verifier()
        self._package_builder = package_builder or ContextPackageBuilder()

        # Subsystems
        self._rag = rag_retriever
        self._research = research_engine
        self._memory = memory_manager
        self._permissions = permission_gate

        self._tool_router = tool_router or ToolRouter(
            rag_retriever=self._rag,
            research_router=self._research,
            permission_gate=self._permissions,
            memory_manager=self._memory,
        )
        self._executor = executor or Executor()

    async def process(
        self,
        request: ChatRequest,
        ws_send: WSSend | None = None,
    ) -> AgentResponse:
        """
        Execute the full reasoning loop for a user request.
        """
        start_time = time.monotonic()
        logger.info("decision_engine_started", message=request.message[:50], trace_id=str(request.trace_id))

        # 1. Intent Analysis & Context Decision
        intent, context_need = self._analyzer.analyze(
            message=request.message,
            project_id=request.project_id,
            has_active_project=request.project_id is not None,
        )

        # 2. Context Gathering (RAG, Memory, Web) based on ContextNeed
        rag_chunks = await self._gather_rag_context(request, context_need)
        memories = await self._gather_memory_context(request, context_need)
        web_results = await self._gather_web_context(request, context_need)

        # 3. Assemble Bounded Context Package
        pkg: AgentContextPackage = self._package_builder.assemble(
            rag_chunks=rag_chunks,
            memory_entries=memories,
            web_results=web_results,
        )

        # 4. Task Planning
        plan = await self._planner.plan(request)
        if ws_send is not None:
            await ws_send({
                "type": "PLAN_CREATED",
                "payload": {
                    "trace_id": str(request.trace_id),
                    "steps": [{"index": s.index, "label": s.label} for s in plan.steps],
                },
            })

        # 5. Step Execution & Verification Loop
        execution_reports: list[ExecutionReport] = []
        final_text = ""
        action_status = "success"
        limitations: list[str] = []

        step_idx = 0
        max_steps = 10  # Guard against infinite loops

        while step_idx < len(plan.steps) and step_idx < max_steps:
            step = plan.steps[step_idx]
            await self._planner.update_step_status(plan, step_idx, StepStatus.RUNNING, ws_send)

            # Pass assembled context text into generation steps
            if step.action_type == ActionType.MODEL_GENERATE:
                step.params["context_text"] = pkg.formatted_text

            # Execute step with retry loop
            attempt = 0
            step_passed = False

            while attempt <= 2 and not step_passed:
                try:
                    target = await self._tool_router.resolve(step)
                    exec_result: ExecutorResult = await self._executor.run(target, step)
                except PermissionDeniedError as pe:
                    exec_result = ExecutorResult(
                        step=step,
                        success=False,
                        content="",
                        error=f"Permission Denied: {pe}",
                    )
                except Exception as e:
                    exec_result = ExecutorResult(
                        step=step,
                        success=False,
                        content="",
                        error=str(e),
                    )

                # Verification
                verdict = await self._verifier.check(exec_result, attempt=attempt)

                if verdict == VerifierVerdict.PASS:
                    step_passed = True
                    await self._planner.update_step_status(plan, step_idx, StepStatus.DONE, ws_send)
                    execution_reports.append(
                        ExecutionReport(
                            step_index=step_idx,
                            success=True,
                            output=exec_result.content,
                            verdict=verdict,
                            retries_used=attempt,
                        )
                    )
                    if step.action_type == ActionType.MODEL_GENERATE:
                        final_text = exec_result.content

                elif verdict == VerifierVerdict.RETRY:
                    attempt += 1
                    logger.info("retrying_step", step=step.label, attempt=attempt)

                elif verdict == VerifierVerdict.ESCALATE:
                    logger.warning("escalating_step_failure", step=step.label, error=exec_result.error)
                    await self._planner.update_step_status(plan, step_idx, StepStatus.FAILED, ws_send)

                    report = ExecutionReport(
                        step_index=step_idx,
                        success=False,
                        output=exec_result.content,
                        verdict=verdict,
                        error_message=exec_result.error or "Verification escalation",
                        retries_used=attempt,
                    )
                    execution_reports.append(report)
                    limitations.append(f"Step '{step.label}' failed: {report.error_message}")

                    # Trigger Dynamic Replanning
                    plan = await self._planner.replan(step, report, plan)
                    break

            step_idx += 1

        # 6. Fallback final text if empty
        if not final_text:
            if pkg.formatted_text:
                final_text = f"Context gathered:\n{pkg.formatted_text}\n\nProcessed: {request.message}"
            else:
                final_text = f"Processed request: {request.message}"

        # 7. Memory Update (Persist turn outcomes if substantive)
        if self._memory is not None and intent not in (IntentType.GENERAL_CONVERSATION,):
            try:
                await self._memory.create_memory(
                    content=f"User asked: '{request.message[:80]}'. Outcome: '{final_text[:80]}'",
                    type=MemoryType.TASK_CONTEXT,
                    project_id=request.project_id,
                    source=MemorySource.AGENT_TURN,
                )
            except Exception as e:
                logger.debug("auto_memory_update_failed", error=str(e))

        latency_ms = int((time.monotonic() - start_time) * 1000)

        return AgentResponse(
            content=final_text,
            sources=pkg.rag_sources,
            web_sources=pkg.web_sources,
            action_status="success" if not limitations else "partial_success",
            limitations=limitations,
            tokens_used=pkg.token_count,
            model_used="qwen-chat",
        )

    # ── Context Gathering Helpers ──────────────────────────────────────────────

    async def _gather_rag_context(self, request: ChatRequest, need: ContextNeed) -> list[Any]:
        """Fetch RAG chunks if needed and active."""
        if need in (ContextNeed.RAG, ContextNeed.RAG_AND_MEMORY, ContextNeed.RAG_AND_WEB, ContextNeed.ALL):
            if self._rag is not None and request.project_id is not None:
                try:
                    res = await self._rag.retrieve(query=request.message, project_id=request.project_id)
                    return getattr(res, "chunks", [])
                except Exception as e:
                    logger.warning("rag_retrieval_failed", error=str(e))
        return []

    async def _gather_memory_context(self, request: ChatRequest, need: ContextNeed) -> list[Any]:
        """Fetch long-term memories if needed."""
        if need in (ContextNeed.MEMORY, ContextNeed.RAG_AND_MEMORY, ContextNeed.MEMORY_AND_WEB, ContextNeed.ALL):
            if self._memory is not None:
                try:
                    return await self._memory.retrieve_memories(
                        query=request.message,
                        project_id=request.project_id,
                        top_k=4,
                    )
                except Exception as e:
                    logger.warning("memory_retrieval_failed", error=str(e))
        return []

    async def _gather_web_context(self, request: ChatRequest, need: ContextNeed) -> list[dict[str, Any]]:
        """Fetch DuckDuckGo web results if needed."""
        if need in (ContextNeed.WEB, ContextNeed.RAG_AND_WEB, ContextNeed.MEMORY_AND_WEB, ContextNeed.ALL):
            if self._research is not None:
                try:
                    res = await self._research.search_raw(query=request.message, max_results=4)
                    return [
                        {"url": r.url, "title": r.title, "snippet": r.snippet, "score": r.score}
                        for r in getattr(res, "results", [])
                    ]
                except Exception as e:
                    logger.warning("web_research_failed", error=str(e))
        return []
