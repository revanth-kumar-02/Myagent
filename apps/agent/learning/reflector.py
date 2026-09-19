"""
learning.reflector — Factual Self-Reflection & Insight Extraction Engine (V12).

Performs evidence-grounded reflection on task outcomes to determine:
  - What worked and what failed
  - Root causes for failures and timeouts
  - Plan complexity and over-engineering detection
  - Actionable candidate learnings for future planning
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from learning.types import (
    ExecutionTrace,
    LearningCategory,
    LearningRecord,
    LearningStatus,
    ReflectionAnalysis,
    StepOutcome,
)

logger = structlog.get_logger(__name__)


class ReflectionEngine:
    """
    Analyzes ExecutionTraces and formulates evidence-based candidate learnings.
    """

    def reflect(self, trace: ExecutionTrace) -> ReflectionAnalysis:
        """
        Evaluate task execution and generate a ReflectionAnalysis with candidate learnings.
        """
        what_worked: list[str] = []
        what_failed: list[str] = []
        improvement_areas: list[str] = []
        candidate_learnings: list[LearningRecord] = []
        root_cause: str | None = None

        # 1. Analyze successful vs failed steps
        for step in trace.actual_steps:
            action_desc = step.tool_name or step.action_type or f"Step {step.step_index}"
            if step.status == "done" and step.verification_verdict == "pass":
                what_worked.append(f"{action_desc} succeeded for goal '{step.goal}' (duration: {step.duration_ms}ms)")
            else:
                failure_desc = f"{action_desc} failed: {step.error or 'verification failed'}"
                what_failed.append(failure_desc)

        # 2. Diagnose Root Cause for Failures
        if trace.final_outcome in ("failed", "partially_completed"):
            root_cause = self._diagnose_root_cause(trace)
            if root_cause:
                improvement_areas.append(f"Address root cause: {root_cause}")

        # 3. Assess Plan Complexity
        is_complex = False
        complexity_notes = ""
        if trace.planned_steps_count > len(trace.actual_steps) + 2:
            is_complex = True
            complexity_notes = f"Planned {trace.planned_steps_count} steps but only {len(trace.actual_steps)} were required."
            improvement_areas.append("Simplify initial plan for similar tasks.")
        elif trace.total_duration_ms > 30000 and len(trace.actual_steps) <= 2:
            is_complex = True
            complexity_notes = "Individual steps incurred long execution latency."

        # 4. Extract Candidate Learnings
        candidate_learnings.extend(self._extract_learnings(trace, root_cause, is_complex))

        analysis = ReflectionAnalysis(
            task_id=trace.task_id,
            what_worked=what_worked,
            what_failed=what_failed,
            root_cause=root_cause,
            improvement_areas=improvement_areas,
            is_plan_overly_complex=is_complex,
            plan_complexity_notes=complexity_notes,
            candidate_learnings=candidate_learnings,
        )

        logger.info(
            "reflection_completed",
            task_id=str(trace.task_id),
            what_worked_count=len(what_worked),
            what_failed_count=len(what_failed),
            learnings_count=len(candidate_learnings),
        )
        return analysis

    def _diagnose_root_cause(self, trace: ExecutionTrace) -> str | None:
        """Classify failure mode based on errors and step outcomes."""
        for step in trace.actual_steps:
            if step.error:
                err_lower = step.error.lower()
                if "permission" in err_lower or "denied" in err_lower:
                    return f"Permission denied on {step.tool_name or 'tool'}: user approval required or restricted access."
                if "timeout" in err_lower:
                    return f"Timeout executing {step.tool_name or 'action'}: task exceeded duration limits."
                if "not found" in err_lower or "no such file" in err_lower:
                    return f"Target resource not found in {step.tool_name or 'step'}: invalid path or identifier."
                if "syntax" in err_lower or "parse" in err_lower:
                    return f"Syntax/Parsing error in {step.tool_name or 'step'}: malformed input or code content."
                return f"Execution error in {step.tool_name or 'step'}: {step.error}"

        if trace.failed_actions:
            return f"Action failure in {', '.join(trace.failed_actions)}."
        return None

    def _extract_learnings(
        self,
        trace: ExecutionTrace,
        root_cause: str | None,
        is_complex: bool,
    ) -> list[LearningRecord]:
        """Formulate specific, actionable learning records from trace evidence."""
        learnings: list[LearningRecord] = []

        # A. Successful Workflow Pattern
        if trace.final_outcome == "success" and len(trace.successful_actions) >= 2:
            actions_seq = " -> ".join(trace.successful_actions)
            learning = LearningRecord(
                category=LearningCategory.SUCCESSFUL_WORKFLOW,
                title=f"Workflow for {trace.goal[:40]}",
                description=f"Effective sequence of tools for goal '{trace.goal}': {actions_seq}",
                condition=f"When executing task with goal matching '{trace.goal[:60]}'",
                recommendation=f"Use action sequence: {actions_seq}",
                confidence=0.9,
                importance=0.6,
                source_task_id=trace.task_id,
                project_id=trace.project_id,
                evidence={
                    "successful_actions": trace.successful_actions,
                    "duration_ms": trace.total_duration_ms,
                    "retries": trace.retries_used,
                },
                status=LearningStatus.ACTIVE,
            )
            learnings.append(learning)

        # B. Failed Workflow / Recovery Strategy
        if trace.final_outcome == "failed" and root_cause:
            learning = LearningRecord(
                category=LearningCategory.FAILED_WORKFLOW,
                title=f"Failure condition for {trace.goal[:40]}",
                description=f"Task failed due to: {root_cause}",
                condition=f"When encountering goal '{trace.goal[:60]}' or error '{root_cause[:50]}'",
                recommendation=f"Avoid failed pattern. Address condition: {root_cause}",
                confidence=0.85,
                importance=0.8,
                source_task_id=trace.task_id,
                project_id=trace.project_id,
                evidence={
                    "failed_actions": trace.failed_actions,
                    "root_cause": root_cause,
                    "error_summary": trace.error_summary,
                },
                status=LearningStatus.ACTIVE,
            )
            learnings.append(learning)

        # C. Recovery Strategy (when retries were needed but task completed)
        if trace.retries_used > 0 and trace.final_outcome in ("success", "partially_completed"):
            learning = LearningRecord(
                category=LearningCategory.RECOVERY_STRATEGY,
                title=f"Recovery strategy for {trace.goal[:40]}",
                description=f"Task required {trace.retries_used} retries before succeeding.",
                condition=f"When executing '{trace.goal[:60]}' and initial attempt fails verification",
                recommendation="Apply retry adjustments or verify step prerequisites before invocation.",
                confidence=0.8,
                importance=0.7,
                source_task_id=trace.task_id,
                project_id=trace.project_id,
                evidence={
                    "retries": trace.retries_used,
                    "successful_actions": trace.successful_actions,
                },
                status=LearningStatus.ACTIVE,
            )
            learnings.append(learning)

        # D. Planning Improvement
        if is_complex:
            learning = LearningRecord(
                category=LearningCategory.PLANNING_IMPROVEMENT,
                title=f"Plan optimization for {trace.goal[:40]}",
                description="Initial plan was overly complex compared to actual execution requirements.",
                condition=f"When planning tasks similar to '{trace.goal[:60]}'",
                recommendation="Construct concise plans with minimal dependency overhead.",
                confidence=0.75,
                importance=0.5,
                source_task_id=trace.task_id,
                project_id=trace.project_id,
                evidence={
                    "planned_steps": trace.planned_steps_count,
                    "actual_steps": len(trace.actual_steps),
                },
                status=LearningStatus.ACTIVE,
            )
            learnings.append(learning)

        return learnings
