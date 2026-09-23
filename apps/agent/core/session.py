"""
core.session — AgentSession

The top-level orchestrator for a single user session.
Wires together the full agent loop:
  ContextManager → Planner → loop(ModelRouter → ToolRouter → Executor → Verifier) → Memory

One AgentSession instance per connected WebSocket client.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog

from core.context import ContextManager
from core.executor import Executor
from core.memory import Memory
from core.model_router import ModelRouter
from core.planner import Planner
from core.tool_router import ToolRouter
from core.types import ActionType, ChatRequest, ChatResponse, Source, VerifierVerdict, WebSource
from core.verifier import Verifier

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession
    from graph.service import KnowledgeGraphService
    from models.registry import ModelRegistry
    from permissions.gate import PermissionGate
    from permissions.types import PermissionGrant
    from rag.retriever import RAGRetriever
    from research.router import ResearchRouter
    from tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class AgentSession:
    """
    Orchestrates the full agent turn loop for one WebSocket session.

    Lifecycle:
      1. Instantiated when a WebSocket connects
      2. run(request) called for each user message
      3. Torn down when WebSocket disconnects
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID | None,
        ws_send: WSSend,
        db: "AsyncSession",
        redis: "aioredis.Redis",
        model_registry: "ModelRegistry",
        rag_retriever: "RAGRetriever",
        research_router: "ResearchRouter",
        tool_registry: "ToolRegistry",
        permission_gate: "PermissionGate",
        failover_manager: Any | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.ws_send = ws_send
        self._failover_manager = failover_manager

        self._model_router = ModelRouter(model_registry, failover_manager=failover_manager)
        self._context = ContextManager(session_id, project_id, db, redis)
        from graph.service import KnowledgeGraphService
        self._graph_service = KnowledgeGraphService(db_session=db)
        self._memory = Memory(
            session_id,
            project_id,
            db,
            redis,
            self._model_router,
            graph_service=self._graph_service,
        )
        self._planner = Planner(self._model_router)
        self._permission_gate = permission_gate
        if getattr(self._permission_gate, "_ws_send", None) is None:
            self._permission_gate._ws_send = ws_send
        self._tool_router = ToolRouter(rag_retriever, research_router, tool_registry, permission_gate)
        self._executor = Executor(ws_send=ws_send, model_router=self._model_router)
        self._verifier = Verifier()
        self._status_listener: Any | None = None

    def handle_permission_response(self, grant: "PermissionGrant") -> None:
        """Handle incoming PERMISSION_RESPONSE frame."""
        self._permission_gate.receive_grant(grant)

    async def start(self) -> None:
        """Load session state and register provider status listener on connection."""
        await self._context.load()

        if self._failover_manager is not None:
            async def _on_provider_status(status_payload: dict[str, Any]) -> None:
                await self.ws_send({
                    "type": "PROVIDER_STATUS",
                    "session_id": str(self.session_id),
                    "payload": status_payload,
                })

            self._failover_manager.add_status_listener(_on_provider_status)
            self._status_listener = _on_provider_status

            # Send initial provider status frame immediately
            await self.ws_send({
                "type": "PROVIDER_STATUS",
                "session_id": str(self.session_id),
                "payload": self._failover_manager.get_status_payload(),
            })

    async def run(self, request: ChatRequest) -> ChatResponse:
        """
        Execute one full agent turn.

        Streams intermediate events (CHAT_CHUNK, TOOL_CALL_NOTIFY, PLAN_UPDATE)
        to the client via ws_send, then returns the final ChatResponse.
        """
        start_time = time.monotonic()
        logger.info("agent_turn_start", session_id=str(self.session_id), trace_id=str(request.trace_id))

        await self._context.append_user(request.message)
        
        memory_context = ""
        try:
            memories = await asyncio.wait_for(self._memory.retrieve(request.message), timeout=1.5)
            memory_context = "\n".join(e.content for e in memories)
        except Exception as e:
            logger.debug("memory_retrieval_skipped_or_timed_out", error=str(e))

        # Load fresh context window
        context = self._context.build(memory_context=memory_context)

        # Plan
        plan = await self._planner.plan(request, context)

        # Autonomous plans are only displayed for multi-step tasks, tools, research, or retrieval
        is_autonomous_plan = (
            len(plan.steps) > 1
            or any(s.action_type in (ActionType.TOOL_CALL, ActionType.WEB_RESEARCH, ActionType.RAG_QUERY, ActionType.MEMORY_QUERY) for s in plan.steps)
        )

        if is_autonomous_plan:
            # Notify UI of created plan
            await self.ws_send({
                "type": "PLAN_UPDATE",
                "payload": {
                    "trace_id": str(plan.trace_id),
                    "steps": [{"index": s.index, "label": s.label, "status": s.status.value} for s in plan.steps],
                },
            })

        sources: list[Source] = []
        web_sources: list[WebSource] = []
        accumulated_context: list[str] = []
        full_text = ""

        # Execute plan steps
        for step in plan.steps:
            if step.action_type == ActionType.MODEL_GENERATE and accumulated_context and "context_text" not in step.params:
                step.params["context_text"] = "\n\n".join(accumulated_context)
            if is_autonomous_plan:
                await self._planner.update_step_status(plan, step.index, step.status.__class__.RUNNING, self.ws_send)
            target = await self._tool_router.resolve(step)
            attempt = 0

            while True:
                result = await self._executor.run(target, step)
                verdict = await self._verifier.check(result, attempt)

                if verdict == VerifierVerdict.PASS:
                    if is_autonomous_plan:
                        await self._planner.update_step_status(plan, step.index, step.status.__class__.DONE, self.ws_send)
                    # Accumulate results
                    if hasattr(result.raw, "sources"):
                        sources.extend(result.raw.sources)
                    if hasattr(result.raw, "web_sources"):
                        web_sources.extend(result.raw.web_sources)
                    if result.content:
                        accumulated_context.append(f"Result of '{step.label}':\n{result.content}")
                        full_text = result.content
                    break
                elif verdict == VerifierVerdict.RETRY:
                    attempt += 1
                    continue
                else:  # ESCALATE
                    if is_autonomous_plan:
                        await self._planner.update_step_status(plan, step.index, step.status.__class__.FAILED, self.ws_send)
                    logger.warning("step_escalated", step=step.label, error=result.error)
                    if result.error:
                        raise RuntimeError(f"Step '{step.label}' failed: {result.error}")
                    break

        if not full_text:
            raise RuntimeError("Inference finished without generating any response text.")

        latency_ms = int((time.monotonic() - start_time) * 1000)
        in_tokens = max(1, len(request.message.split()) * 2)
        out_tokens = max(1, len(full_text.split()) * 2)

        chat_config = self._model_router.get_config("chat")
        model_name = chat_config.name if chat_config else "qwen-chat"

        response = ChatResponse(
            full_text=full_text,
            sources=sources,
            web_sources=web_sources,
            model_used=model_name,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=latency_ms,
        )

        await self._context.append_assistant(full_text)
        try:
            await asyncio.wait_for(self._memory.persist(request.message, full_text), timeout=1.5)
        except Exception as e:
            logger.debug("memory_persist_skipped_or_timed_out", error=str(e))

        await self._context.save()
        return response

    async def stop(self) -> None:
        """Save session state on disconnect."""
        await self._context.save()
