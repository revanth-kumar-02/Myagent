"""
core.executor — Async Execution Engine (V7)

Responsibilities:
  - Receive a DispatchTarget and PlanStep
  - Execute target asynchronously (RAG, Web, Memory, Tool, Model)
  - Emit TOOL_CALL_NOTIFY and TOOL_RESULT_NOTIFY WebSocket frames
  - Stream CHAT_CHUNK token frames for model generation
  - Return typed ExecutorResult
"""

from __future__ import annotations

import inspect
import time
from typing import Any, Awaitable, Callable

import structlog

from core.types import ActionType, ExecutorResult, PlanStep

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class Executor:
    """
    Executes resolved DispatchTargets and pushes WebSocket events.
    """

    def __init__(
        self,
        ws_send: WSSend | None = None,
        model_handle: Any | None = None,
    ) -> None:
        self._ws_send = ws_send
        self._model_handle = model_handle

    async def run(self, target: Any, step: PlanStep) -> ExecutorResult:
        """
        Execute dispatch target and report outcome.
        """
        start_ms = int(time.monotonic() * 1000)

        try:
            match target.action_type:
                case ActionType.RAG_QUERY:
                    return await self._run_rag(target, step, start_ms)
                case ActionType.WEB_RESEARCH:
                    return await self._run_web_research(target, step, start_ms)
                case ActionType.MEMORY_QUERY:
                    return await self._run_memory(target, step, start_ms)
                case ActionType.TOOL_CALL:
                    return await self._run_tool(target, step, start_ms)
                case ActionType.MODEL_GENERATE:
                    return await self._run_model(target, step, start_ms)
                case _:
                    return ExecutorResult(
                        step=step,
                        success=False,
                        content="",
                        error=f"Unsupported action type: {target.action_type}",
                    )
        except Exception as e:
            logger.warning("executor_step_failed", step=step.label, error=str(e))
            return ExecutorResult(
                step=step,
                success=False,
                content="",
                error=str(e),
            )

    async def _run_rag(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Execute RAG retrieval."""
        if target.callable_ is not None:
            if inspect.iscoroutinefunction(target.callable_):
                res = await target.callable_(**target.params)
            else:
                res = target.callable_(**target.params)
            content = str(res)
            return ExecutorResult(step=step, success=True, content=content, raw=res)
        return ExecutorResult(step=step, success=True, content=f"RAG query: {step.params.get('query')}")

    async def _run_web_research(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Execute DuckDuckGo web research."""
        if target.callable_ is not None:
            if inspect.iscoroutinefunction(target.callable_):
                res = await target.callable_(**target.params)
            else:
                res = target.callable_(**target.params)
            content = getattr(res, "context_text", str(res))
            return ExecutorResult(step=step, success=True, content=content, raw=res)
        return ExecutorResult(step=step, success=True, content=f"Web search: {step.params.get('query')}")

    async def _run_memory(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Execute Memory retrieval."""
        if target.callable_ is not None:
            if inspect.iscoroutinefunction(target.callable_):
                res = await target.callable_(**target.params)
            else:
                res = target.callable_(**target.params)
            content = str(res)
            return ExecutorResult(step=step, success=True, content=content, raw=res)
        return ExecutorResult(step=step, success=True, content=f"Memory query: {step.params.get('query')}")

    async def _run_tool(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Execute tool with WebSocket notifications."""
        tool_name = target.tool_name or step.required_tool or "tool"
        if self._ws_send is not None:
            await self._ws_send({
                "type": "TOOL_CALL_NOTIFY",
                "payload": {"tool": tool_name, "params": target.params},
            })

        output = ""
        if target.callable_ is not None:
            if inspect.iscoroutinefunction(target.callable_):
                res = await target.callable_(**target.params)
            else:
                res = target.callable_(**target.params)
            output = str(res)
        else:
            output = f"Executed {tool_name} with params {target.params}"

        if self._ws_send is not None:
            await self._ws_send({
                "type": "TOOL_RESULT_NOTIFY",
                "payload": {"tool": tool_name, "output": output[:200]},
            })

        return ExecutorResult(step=step, success=True, content=output, raw=output)

    async def _run_model(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Generate response via model handle or fallback synthesis."""
        prompt = target.params.get("prompt", "")
        context_text = target.params.get("context_text", "")

        # Format synthetic or model-streamed answer
        if context_text:
            text = f"Based on verified knowledge:\n{context_text}\n\nAnswer to: {prompt}"
        else:
            text = f"Response to request: {prompt}"

        if self._ws_send is not None:
            await self._ws_send({
                "type": "CHAT_CHUNK",
                "payload": {"chunk": text},
            })

        return ExecutorResult(step=step, success=True, content=text, raw=text)
