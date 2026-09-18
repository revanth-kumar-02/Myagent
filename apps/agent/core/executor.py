"""
core.executor — Executor

Responsibilities:
  - Receive a DispatchTarget from the ToolRouter
  - Execute the target asynchronously
  - Stream token chunks over WebSocket for model_generate actions
  - Emit TOOL_CALL_NOTIFY and TOOL_RESULT_NOTIFY WebSocket messages for tool calls
  - Return a typed ExecutorResult

The Executor knows nothing about planning or context assembly.
It only executes what it is given and reports what happened.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, AsyncIterator, Callable, Awaitable

import structlog

from core.types import ActionType, ExecutorResult, PlanStep

if TYPE_CHECKING:
    from core.tool_router import DispatchTarget

logger = structlog.get_logger(__name__)

# Type alias for the WebSocket send function
WSSend = Callable[[dict], Awaitable[None]]


class Executor:
    """
    Async dispatcher — executes a resolved DispatchTarget and streams results.

    ws_send: async function to push JSON frames to the connected WebSocket client.
    """

    def __init__(self, ws_send: WSSend) -> None:
        self._ws_send = ws_send

    async def run(self, target: "DispatchTarget", step: PlanStep) -> ExecutorResult:
        """
        Execute the dispatch target and return a result.

        For ActionType.MODEL_GENERATE: streams CHAT_CHUNK frames and returns
        the assembled full text.

        For ActionType.TOOL_CALL: emits TOOL_CALL_NOTIFY before, TOOL_RESULT_NOTIFY
        after, and returns the tool result.

        For ActionType.RAG_QUERY / WEB_RESEARCH: calls the subsystem and returns
        the context string.
        """
        start_ms = int(time.monotonic() * 1000)

        match target.action_type:
            case ActionType.RAG_QUERY:
                return await self._run_rag(target, step, start_ms)
            case ActionType.WEB_RESEARCH:
                return await self._run_web_research(target, step, start_ms)
            case ActionType.TOOL_CALL:
                return await self._run_tool(target, step, start_ms)
            case ActionType.MODEL_GENERATE:
                return await self._run_model(target, step, start_ms)
            case _:
                raise ValueError(f"Unknown action type: {target.action_type}")

    # ── Private dispatch methods (stubs) ──────────────────────────────────────

    async def _run_rag(self, target: "DispatchTarget", step: PlanStep, start_ms: int) -> ExecutorResult:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _run_web_research(self, target: "DispatchTarget", step: PlanStep, start_ms: int) -> ExecutorResult:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _run_tool(self, target: "DispatchTarget", step: PlanStep, start_ms: int) -> ExecutorResult:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _run_model(self, target: "DispatchTarget", step: PlanStep, start_ms: int) -> ExecutorResult:
        raise NotImplementedError  # TODO: implement in feature phase
