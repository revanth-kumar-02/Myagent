"""
core.session — AgentSession

The top-level orchestrator for a single user session.
Wires together the full agent loop:
  ContextManager → Planner → loop(ModelRouter → ToolRouter → Executor → Verifier) → Memory

One AgentSession instance per connected WebSocket client.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Callable, Awaitable

import structlog

from core.context import ContextManager
from core.executor import Executor
from core.memory import Memory
from core.model_router import ModelRouter
from core.planner import Planner
from core.tool_router import ToolRouter
from core.types import ChatRequest, ChatResponse, VerifierVerdict
from core.verifier import Verifier

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession
    from models.registry import ModelRegistry
    from permissions.gate import PermissionGate
    from rag.retriever import RAGRetriever
    from research.router import ResearchRouter
    from tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict], Awaitable[None]]


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
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id

        self._model_router = ModelRouter(model_registry)
        self._context = ContextManager(session_id, project_id, db, redis)
        self._memory = Memory(session_id, project_id, db, redis, self._model_router)
        self._planner = Planner(self._model_router)
        self._tool_router = ToolRouter(rag_retriever, research_router, tool_registry, permission_gate)
        self._executor = Executor(ws_send)
        self._verifier = Verifier()

    async def start(self) -> None:
        """Load session state on connection."""
        await self._context.load()

    async def run(self, request: ChatRequest) -> ChatResponse:
        """
        Execute one full agent turn.

        Streams intermediate events (CHAT_CHUNK, TOOL_CALL_NOTIFY, PLAN_UPDATE)
        to the client via ws_send, then returns the final ChatResponse.
        """
        logger.info("agent_turn_start", session_id=str(self.session_id), trace_id=str(request.trace_id))

        await self._context.append_user(request.message)
        memory_context = "\n".join(e.content for e in await self._memory.retrieve(request.message))

        # Load fresh context window
        context = self._context.build(memory_context=memory_context)

        # Plan
        plan = await self._planner.plan(request, context)

        sources = []
        web_sources = []
        full_text = ""

        # Execute plan steps
        for step in plan.steps:
            target = await self._tool_router.resolve(step)
            attempt = 0

            while True:
                result = await self._executor.run(target, step)
                verdict = await self._verifier.check(result, attempt)

                if verdict == VerifierVerdict.PASS:
                    # Accumulate results
                    if hasattr(result.raw, "sources"):
                        sources.extend(result.raw.sources)
                    if hasattr(result.raw, "web_sources"):
                        web_sources.extend(result.raw.web_sources)
                    if result.content:
                        full_text = result.content
                    break
                elif verdict == VerifierVerdict.RETRY:
                    attempt += 1
                    continue
                else:  # ESCALATE
                    logger.warning("step_escalated", step=step.label)
                    break

        response = ChatResponse(
            full_text=full_text,
            sources=sources,
            web_sources=web_sources,
            model_used="",     # populated by executor in feature phase
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
        )

        await self._context.append_assistant(full_text)
        await self._memory.persist(request.message, full_text)
        await self._context.save()

        return response

    async def stop(self) -> None:
        """Save session state on disconnect."""
        await self._context.save()
