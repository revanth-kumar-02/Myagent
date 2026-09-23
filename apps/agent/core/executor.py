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
        """Execute DuckDuckGo web research with offline awareness."""
        is_online = True
        if self._model_router and hasattr(self._model_router, "failover_manager"):
            is_online = self._model_router.failover_manager.is_internet_available
            if not is_online:
                is_online = await self._model_router.failover_manager.check_internet()

        if not is_online:
            offline_msg = (
                "I'm currently offline, so Internet research is unavailable. "
                "I can still assist you with local files, system information, applications, and other local tools."
            )
            return ExecutorResult(
                step=step,
                success=True,
                content=offline_msg,
                raw={"offline": True, "requires_network": True, "reason": "no_internet"},
            )

        if target.callable_ is not None:
            try:
                if inspect.iscoroutinefunction(target.callable_):
                    res = await target.callable_(**target.params)
                else:
                    res = target.callable_(**target.params)
                content = getattr(res, "context_text", str(res))
                return ExecutorResult(step=step, success=True, content=content, raw=res)
            except Exception as e:
                logger.warning("web_research_error", error=str(e))
                return ExecutorResult(
                    step=step,
                    success=True,
                    content=f"Internet research is currently unavailable ({e}). You can proceed using local tools.",
                    raw={"error": str(e)},
                )
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
        """Execute tool with WebSocket notifications and offline availability checks."""
        tool_name = target.tool_name or step.required_tool or "tool"
        tool_inst = getattr(target, "tool_instance", None)

        # Check offline tool requirements
        if tool_inst is not None and getattr(tool_inst, "requires_network", False):
            is_online = True
            if self._model_router and hasattr(self._model_router, "failover_manager"):
                is_online = self._model_router.failover_manager.is_internet_available
            if not is_online:
                unavailable_msg = (
                    f"Tool '{tool_name}' requires active Internet connectivity and is unavailable offline. "
                    "Local tools (system_info, clipboard, app_launcher, files, dev tools) remain fully operational."
                )
                return ExecutorResult(
                    step=step,
                    success=True,
                    content=unavailable_msg,
                    raw={"tool": tool_name, "requires_network": True, "available_offline": False},
                )

        if self._ws_send is not None:
            await self._ws_send({
                "type": "TOOL_CALL_NOTIFY",
                "payload": {"tool": tool_name, "params": target.params},
            })

        output = ""
        res: Any = None
        if target.callable_ is not None:
            try:
                sig = inspect.signature(target.callable_)
                param_names = list(sig.parameters.keys())

                if "params" in param_names or (len(param_names) == 1 and list(sig.parameters.values())[0].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)):
                    if inspect.iscoroutinefunction(target.callable_):
                        res = await target.callable_(target.params)
                    else:
                        res = target.callable_(target.params)
                else:
                    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                    call_kwargs = target.params if has_varkw else {k: v for k, v in target.params.items() if k in param_names}
                    if inspect.iscoroutinefunction(target.callable_):
                        res = await target.callable_(**call_kwargs)
                    else:
                        res = target.callable_(**call_kwargs)
            except Exception as e:
                logger.warning("tool_invocation_error", tool=tool_name, error=str(e))
                return ExecutorResult(step=step, success=False, content="", error=str(e))

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
