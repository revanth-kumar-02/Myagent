"""
core.planner — Context-Aware Planner (RAG V4)

Responsibilities:
  - Analyze user requests using ContextResolver
  - Decompose requests into an ordered list of PlanSteps:
      - RAG_QUERY: retrieve project knowledge
      - WEB_RESEARCH: search external web
      - MEMORY_QUERY: retrieve personal preferences / facts
      - MODEL_GENERATE: produce grounded response
  - Keep plans minimal for simple queries (single generation step)
  - Send PLAN_UPDATE WebSocket events as step status changes
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog

from core.context_resolver import ContextResolver
from core.types import ActionType, Plan, PlanStep, SourceType, StepStatus

if TYPE_CHECKING:
    from core.types import ChatRequest, ContextWindow

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class Planner:
    """
    Converts a user request into an executable step Plan.
    """

    def __init__(self, model_router: object | None = None) -> None:
        self._model_router = model_router
        self._resolver = ContextResolver()

    async def plan(
        self,
        request: "ChatRequest",
        context: "ContextWindow | None" = None,
    ) -> Plan:
        """
        Produce a Plan based on the user request and resolved context sources.
        """
        sources = self._resolver.resolve(
            message=request.message,
            project_id=request.project_id,
            has_active_project=request.project_id is not None,
        )

        steps: list[PlanStep] = []
        step_idx = 0

        # 1. RAG retrieval step if needed
        if SourceType.RAG in sources and request.project_id is not None:
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Retrieve project knowledge",
                    action_type=ActionType.RAG_QUERY,
                    params={"query": request.message, "project_id": str(request.project_id)},
                )
            )
            step_idx += 1

        # 2. Web research step if needed
        if SourceType.WEB in sources:
            steps.append(
                PlanStep(
                    index=step_idx,
                    label="Search external web sources",
                    action_type=ActionType.WEB_RESEARCH,
                    params={"query": request.message},
                )
            )
            step_idx += 1

        # 3. Final model generation step
        steps.append(
            PlanStep(
                index=step_idx,
                label="Generate grounded response",
                action_type=ActionType.MODEL_GENERATE,
                params={"prompt": request.message},
            )
        )

        return Plan(steps=steps, trace_id=request.trace_id)

    async def update_step_status(
        self,
        plan: Plan,
        step_index: int,
        status: StepStatus,
        ws_send: WSSend | None = None,
    ) -> None:
        """
        Update a step's status and optionally emit a PLAN_UPDATE WebSocket message.
        """
        if 0 <= step_index < len(plan.steps):
            plan.steps[step_index].status = status
            if ws_send is not None:
                await ws_send({
                    "type": "PLAN_UPDATE",
                    "payload": {
                        "trace_id": str(plan.trace_id),
                        "step_index": step_index,
                        "status": status.value,
                        "label": plan.steps[step_index].label,
                    },
                })
