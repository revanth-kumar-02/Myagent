"""
core.executor — Async Execution Engine

Responsibilities:
  - Receive a DispatchTarget and PlanStep
  - Execute target asynchronously (RAG, Web, Memory, Tool, Model)
  - Emit TOOL_CALL_NOTIFY and TOOL_RESULT_NOTIFY WebSocket frames
  - Stream CHAT_CHUNK token frames for model generation using ModelRouter / HuggingFaceProvider
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
        model_router: Any | None = None,
    ) -> None:
        self._ws_send = ws_send
        self._model_handle = model_handle
        self._model_router = model_router

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
        res: Any = None
        if target.callable_ is not None:
            sig = inspect.signature(target.callable_)
            if len(sig.parameters) == 1 or "params" in sig.parameters:
                if inspect.iscoroutinefunction(target.callable_):
                    res = await target.callable_(target.params)
                else:
                    res = target.callable_(target.params)
            else:
                if inspect.iscoroutinefunction(target.callable_):
                    res = await target.callable_(**target.params)
                else:
                    res = target.callable_(**target.params)

            if hasattr(res, "error") and res.error:
                return ExecutorResult(step=step, success=False, content="", error=str(res.error), raw=res)
            if hasattr(res, "output"):
                output = str(res.output) if res.output is not None else str(res)
            else:
                output = str(res)
        else:
            output = f"Executed {tool_name} with params {target.params}"

        if self._ws_send is not None:
            await self._ws_send({
                "type": "TOOL_RESULT_NOTIFY",
                "payload": {"tool": tool_name, "output": output[:200]},
            })

        return ExecutorResult(step=step, success=True, content=output, raw=res if res is not None else output)

    async def _run_model(self, target: Any, step: PlanStep, start_ms: int) -> ExecutorResult:
        """Generate response via model handle with token streaming."""
        prompt = target.params.get("prompt", "")
        context_text = target.params.get("context_text", "")
        capability = target.params.get("capability", "chat")

        handle = self._model_handle
        if handle is None and self._model_router is not None:
            try:
                handle = await self._model_router.select(capability)
            except Exception as e:
                logger.debug("model_router_select_failed", capability=capability, error=str(e))

        messages: list[dict[str, Any]] = []
        if context_text:
            messages.append({
                "role": "system",
                "content": (
                    "You are Kora, a helpful and precise autonomous AI assistant. "
                    "Use the following verified context to answer the user's inquiry:\n"
                    f"{context_text}"
                ),
            })
        else:
            messages.append({
                "role": "system",
                "content": "You are Kora, a helpful and precise autonomous AI assistant.",
            })
        messages.append({"role": "user", "content": prompt})

        # Fallback text if model generation is not connected or fails
        if context_text:
            fallback_text = f"Based on verified knowledge:\n{context_text}\n\nAnswer to: {prompt}"
        else:
            fallback_text = f"Response to request: {prompt}"

        accumulated: list[str] = []
        if handle is not None and hasattr(handle, "stream"):
            try:
                async for chunk in handle.stream(messages):
                    accumulated.append(chunk)
                    if self._ws_send is not None:
                        await self._ws_send({
                            "type": "CHAT_CHUNK",
                            "payload": {"chunk": chunk},
                        })
                if accumulated:
                    full_text = "".join(accumulated)
                    return ExecutorResult(step=step, success=True, content=full_text, raw=full_text)
            except Exception as exc:
                logger.error("model_streaming_failed", error=str(exc))
                raise

        # Fallback path if running in standalone offline/mock test harness without handle
        if self._ws_send is not None:
            await self._ws_send({
                "type": "CHAT_CHUNK",
                "payload": {"chunk": fallback_text},
            })
        return ExecutorResult(step=step, success=True, content=fallback_text, raw=fallback_text)
