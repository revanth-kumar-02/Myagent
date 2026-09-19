"""
learning.analyzer — Execution Trace & Task Performance Analyzer (V12).

Transforms step execution records, tool responses, and verification results into a structured ExecutionTrace.
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

import structlog

from learning.types import ExecutionTrace, StepOutcome

logger = structlog.get_logger(__name__)


class ExecutionAnalyzer:
    """
    Analyzes step-by-step task execution to build a comprehensive ExecutionTrace.
    """

    def analyze_execution(
        self,
        task_id: uuid.UUID,
        goal: str,
        step_outcomes: Sequence[StepOutcome | dict[str, Any]],
        project_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        planned_steps_count: int | None = None,
    ) -> ExecutionTrace:
        """
        Synthesize step outcomes into a normalized ExecutionTrace.
        """
        normalized_steps: list[StepOutcome] = []
        successful_actions: list[str] = []
        failed_actions: list[str] = []
        total_retries = 0
        total_duration = 0
        errors: list[str] = []

        for so in step_outcomes:
            if isinstance(so, dict):
                outcome = StepOutcome(
                    step_index=int(so.get("step_index", 0)),
                    goal=str(so.get("goal", "")),
                    tool_name=so.get("tool_name"),
                    action_type=str(so.get("action_type", "")),
                    status=str(so.get("status", "done")),
                    output=so.get("output"),
                    error=so.get("error"),
                    duration_ms=int(so.get("duration_ms", 0)),
                    verification_verdict=str(so.get("verification_verdict", "pass")),
                    retry_count=int(so.get("retry_count", 0)),
                    params=so.get("params", {}),
                )
            else:
                outcome = so

            normalized_steps.append(outcome)
            total_duration += outcome.duration_ms
            total_retries += outcome.retry_count

            action_label = outcome.tool_name or outcome.action_type or f"step_{outcome.step_index}"

            if outcome.status == "done" and outcome.verification_verdict == "pass":
                successful_actions.append(action_label)
            else:
                failed_actions.append(action_label)
                if outcome.error:
                    errors.append(f"{action_label}: {outcome.error}")

        # Determine overall task outcome
        if not normalized_steps:
            final_outcome = "success"
        elif not failed_actions:
            final_outcome = "success"
        elif successful_actions:
            final_outcome = "partially_completed"
        else:
            final_outcome = "failed"

        error_summary = " | ".join(errors) if errors else None
        planned_count = planned_steps_count or len(normalized_steps)

        trace = ExecutionTrace(
            task_id=task_id,
            goal=goal,
            planned_steps_count=planned_count,
            actual_steps=normalized_steps,
            successful_actions=successful_actions,
            failed_actions=failed_actions,
            retries_used=total_retries,
            total_duration_ms=total_duration,
            final_outcome=final_outcome,
            error_summary=error_summary,
            project_id=project_id,
            session_id=session_id,
        )

        logger.debug(
            "execution_trace_analyzed",
            task_id=str(task_id),
            outcome=final_outcome,
            steps=len(normalized_steps),
            retries=total_retries,
        )
        return trace
