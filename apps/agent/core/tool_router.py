"""
core.tool_router — Tool Router

Responsibilities:
  - Classify each PlanStep's ActionType into the concrete subsystem to invoke
  - Enforce the PermissionGate before any tool dispatch
  - Resolve tool names to registered BaseTool instances
  - Never execute tools directly — dispatch to Executor

Dispatch table:
  ActionType.RAG_QUERY      → RAGEngine.query()
  ActionType.WEB_RESEARCH   → ResearchRouter.search()
  ActionType.TOOL_CALL      → PermissionGate → ToolRegistry.get(name).execute()
  ActionType.MODEL_GENERATE → HuggingFaceProvider.stream()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from core.types import ActionType, ExecutorResult, PlanStep

if TYPE_CHECKING:
    from permissions.gate import PermissionGate
    from rag.retriever import RAGRetriever
    from research.router import ResearchRouter
    from tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class ToolRouter:
    """
    Determines which subsystem handles a given PlanStep and enforces permissions.
    Returns a configured dispatch callable for the Executor to invoke.
    """

    def __init__(
        self,
        rag_retriever: "RAGRetriever",
        research_router: "ResearchRouter",
        tool_registry: "ToolRegistry",
        permission_gate: "PermissionGate",
    ) -> None:
        self._rag = rag_retriever
        self._research = research_router
        self._tools = tool_registry
        self._permissions = permission_gate

    async def resolve(self, step: PlanStep) -> "DispatchTarget":
        """
        Returns a DispatchTarget describing what to call and with what args.
        Raises PermissionDeniedError if the step requires a permission not yet granted.
        """
        raise NotImplementedError  # TODO: implement in feature phase


class DispatchTarget:
    """Encapsulates a resolved, permission-checked execution target."""

    action_type: ActionType
    callable_: object    # async callable
    params: dict

    def __init__(self, action_type: ActionType, callable_: object, params: dict) -> None:
        self.action_type = action_type
        self.callable_ = callable_
        self.params = params


class PermissionDeniedError(Exception):
    """Raised when the PermissionGate blocks a tool invocation."""
