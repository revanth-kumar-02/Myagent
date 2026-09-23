"""
core.tool_router — Tool Router & Subsystem Dispatcher (V7)

Responsibilities:
  - Classify each PlanStep's ActionType into the concrete subsystem to invoke
  - Enforce PermissionGate before any tool dispatch (never bypass permissions)
  - Resolve tool names to registered BaseTool instances
  - Package target into a typed DispatchTarget
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import structlog

from core.types import ActionType, PlanStep

if TYPE_CHECKING:
    from memory.manager import MemoryManager
    from permissions.gate import PermissionGate
    from rag.retriever import RAGRetriever
    from research.router import ResearchRouter
    from tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class PermissionDeniedError(Exception):
    """Raised when the PermissionGate blocks a tool invocation."""


class DispatchTarget:
    """Encapsulates a resolved, permission-checked execution target."""

    def __init__(
        self,
        action_type: ActionType,
        callable_: Callable[..., Any] | None,
        params: dict[str, Any],
        tool_name: str | None = None,
        tool_instance: Any | None = None,
    ) -> None:
        self.action_type = action_type
        self.callable_ = callable_
        self.params = params
        self.tool_name = tool_name
        self.tool_instance = tool_instance


class ToolRouter:
    """
    Determines which subsystem handles a given PlanStep and enforces permissions.
    """

    def __init__(
        self,
        rag_retriever: Any | None = None,
        research_router: Any | None = None,
        tool_registry: Any | None = None,
        permission_gate: Any | None = None,
        memory_manager: Any | None = None,
    ) -> None:
        self._rag = rag_retriever
        self._research = research_router
        self._tools = tool_registry
        self._permissions = permission_gate
        self._memory = memory_manager

    async def resolve(self, step: PlanStep) -> DispatchTarget:
        """
        Resolves a PlanStep into a DispatchTarget.
        Enforces PermissionGate for tool calls.
        """
        match step.action_type:
            case ActionType.RAG_QUERY:
                return DispatchTarget(
                    action_type=ActionType.RAG_QUERY,
                    callable_=getattr(self._rag, "retrieve", None),
                    params=step.params,
                )

            case ActionType.WEB_RESEARCH:
                return DispatchTarget(
                    action_type=ActionType.WEB_RESEARCH,
                    callable_=getattr(self._research, "search", None),
                    params=step.params,
                )

            case ActionType.MEMORY_QUERY:
                return DispatchTarget(
                    action_type=ActionType.MEMORY_QUERY,
                    callable_=getattr(self._memory, "retrieve_memories", None),
                    params=step.params,
                )

            case ActionType.TOOL_CALL:
                tool_name = step.required_tool or step.params.get("tool") or "general_tool"
                tool_instance = None
                if self._tools is not None and hasattr(self._tools, "get"):
                    try:
                        tool_instance = self._tools.get(tool_name)
                    except Exception:
                        pass

                # Check permission gate
                if self._permissions is not None and tool_instance is not None:
                    try:
                        await self._permissions.check(tool_instance)
                    except Exception as e:
                        logger.warning("permission_gate_blocked_tool", tool=tool_name, error=str(e))
                        raise PermissionDeniedError(f"Permission denied for tool: {tool_name}") from e

                return DispatchTarget(
                    action_type=ActionType.TOOL_CALL,
                    callable_=getattr(tool_instance, "run", getattr(tool_instance, "execute", None)) if tool_instance else None,
                    params=step.params,
                    tool_name=tool_name,
                    tool_instance=tool_instance,
                )

            case ActionType.MODEL_GENERATE:
                return DispatchTarget(
                    action_type=ActionType.MODEL_GENERATE,
                    callable_=None,  # Handled by executor with model handle
                    params=step.params,
                )

            case _:
                raise ValueError(f"Unknown action type: {step.action_type}")
