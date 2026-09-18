"""
core.planner — Planner

Responsibilities:
  - Decompose a user message into an ordered list of PlanSteps
  - Each step specifies: ActionType, label, and parameters
  - Send PLAN_UPDATE WebSocket events as step status changes
  - Does NOT execute steps — that is the Executor's job

The planner uses the reasoning model (capability: "reason") to produce
a structured JSON step plan, then validates and returns it as a Plan.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, AsyncIterator

import structlog

from core.types import ActionType, Plan, PlanStep, StepStatus

if TYPE_CHECKING:
    from core.types import ChatRequest, ContextWindow

logger = structlog.get_logger(__name__)


class Planner:
    """
    Converts a user request into an executable step Plan.

    The plan is intentionally minimal for simple requests (single step)
    and expands for multi-step reasoning or tool-use scenarios.
    """

    def __init__(self, model_router: object) -> None:
        # model_router injected to avoid circular imports
        self._model_router = model_router

    async def plan(
        self,
        request: "ChatRequest",
        context: "ContextWindow",
    ) -> Plan:
        """
        Produce a Plan from the user request and current context.

        Returns a Plan with one or more PlanSteps. Each step has an ActionType
        that the ToolRouter will use to dispatch execution.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def update_step_status(
        self,
        plan: Plan,
        step_index: int,
        status: StepStatus,
        ws_send: object,  # Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        Update a step's status and emit a PLAN_UPDATE WebSocket message.
        ws_send is the bound WebSocket send function for the current session.
        """
        plan.steps[step_index].status = status
        raise NotImplementedError  # TODO: emit WS event in feature phase
