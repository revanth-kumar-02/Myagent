"""
vision.workflows.engine — Visual Workflow Automation Execution Engine (V20)

Executes multi-step visual workflows using real-time screen understanding,
visual grounding, permission checks, closed-loop verification, and loop prevention.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any

import structlog

from permissions.gate import PermissionDeniedError, PermissionGate
from tools.computer import KeyboardControlTool, MouseControlTool, WindowManagerTool
from vision.analyzer import VisualUnderstandingEngine
from vision.capture import ScreenCaptureEngine
from vision.grounding import VisualGroundingEngine
from vision.types import CaptureOptions, CaptureTarget, VerificationStatus
from vision.workflows.conditions import VisualConditionEvaluator
from vision.workflows.types import (
    StepExecutionRecord,
    VisualActionType,
    VisualWorkflow,
    VisualWorkflowStep,
    WorkflowExecutionResult,
    WorkflowStatus,
)

logger = structlog.get_logger(__name__)

# Secret sanitization pattern to ensure secret variables cannot be injected
_FORBIDDEN_SECRET_NAMES = {"password", "passwd", "token", "secret", "api_key", "auth_token"}


class VisualWorkflowEngine:
    """
    Core executor for multi-step visual workflows.
    """

    def __init__(
        self,
        capture_engine: ScreenCaptureEngine | None = None,
        analyzer: VisualUnderstandingEngine | None = None,
        grounding_engine: VisualGroundingEngine | None = None,
        condition_evaluator: VisualConditionEvaluator | None = None,
        permission_gate: PermissionGate | None = None,
        mouse_tool: MouseControlTool | None = None,
        keyboard_tool: KeyboardControlTool | None = None,
        window_tool: WindowManagerTool | None = None,
        max_total_steps: int = 50,
    ) -> None:
        self._capture = capture_engine or ScreenCaptureEngine()
        self._analyzer = analyzer or VisualUnderstandingEngine()
        self._grounding = grounding_engine or VisualGroundingEngine()
        self._conditions = condition_evaluator or VisualConditionEvaluator()
        self._gate = permission_gate
        self._mouse = mouse_tool or MouseControlTool()
        self._keyboard = keyboard_tool or KeyboardControlTool()
        self._window = window_tool or WindowManagerTool()
        self._max_total_steps = max_total_steps

    def _interpolate_variables(self, text: str | None, variables: dict[str, str]) -> str:
        """Interpolate {{var_name}} templates within text."""
        if not text:
            return ""
        result = text
        for key, val in variables.items():
            if key.lower() in _FORBIDDEN_SECRET_NAMES:
                continue  # Never interpolate prohibited raw secrets
            result = result.replace(f"{{{{{key}}}}}", str(val))
        return result

    async def execute_workflow(
        self,
        workflow: VisualWorkflow,
        runtime_variables: dict[str, str] | None = None,
        mock_pre_elements: list[dict[str, Any]] | None = None,
    ) -> WorkflowExecutionResult:
        """
        Execute all steps of a visual workflow sequentially with branching and retries.
        """
        exec_id = f"wfx_{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()

        # Merge variables
        variables = dict(workflow.variables)
        if runtime_variables:
            variables.update(runtime_variables)

        step_records: list[StepExecutionRecord] = []
        step_map = {s.step_id: s for s in workflow.steps}
        current_step_idx = 0
        total_steps_executed = 0

        logger.info("visual_workflow_started", execution_id=exec_id, workflow=workflow.name, steps_count=len(workflow.steps))

        while current_step_idx < len(workflow.steps):
            # Loop Prevention Guard
            if total_steps_executed >= self._max_total_steps:
                error_msg = f"Loop prevention triggered: exceeded max limit of {self._max_total_steps} steps."
                logger.error("workflow_loop_prevented", execution_id=exec_id, total_steps=total_steps_executed)
                return WorkflowExecutionResult(
                    execution_id=exec_id,
                    workflow_id=workflow.workflow_id,
                    workflow_name=workflow.name,
                    status=WorkflowStatus.FAILED,
                    step_records=step_records,
                    variables_used=variables,
                    error_message=error_msg,
                    duration_seconds=time.monotonic() - start_time,
                )

            step = workflow.steps[current_step_idx]
            total_steps_executed += 1

            # Execute single step with retries
            record = await self._execute_step(
                step=step,
                variables=variables,
                previous_record=step_records[-1] if step_records else None,
                mock_pre_elements=mock_pre_elements,
            )
            step_records.append(record)

            if record.executed and record.verification_status in {VerificationStatus.SUCCESS, VerificationStatus.INDETERMINATE}:
                # Proceed to next sequential step
                current_step_idx += 1
            else:
                # Step failed after retries: Check failure branching
                if step.on_failure_branch_to_step and step.on_failure_branch_to_step in step_map:
                    logger.info("workflow_branching_on_failure", from_step=step.step_id, to_step=step.on_failure_branch_to_step)
                    # Find index of target branch step
                    target_idx = next(i for i, s in enumerate(workflow.steps) if s.step_id == step.on_failure_branch_to_step)
                    current_step_idx = target_idx
                else:
                    # Workflow fails
                    logger.error("visual_workflow_failed_at_step", step=step.step_id, error=record.error_message)
                    return WorkflowExecutionResult(
                        execution_id=exec_id,
                        workflow_id=workflow.workflow_id,
                        workflow_name=workflow.name,
                        status=WorkflowStatus.FAILED,
                        step_records=step_records,
                        variables_used=variables,
                        error_message=f"Step '{step.name}' failed: {record.error_message}",
                        duration_seconds=time.monotonic() - start_time,
                    )

        # Successfully finished all steps
        return WorkflowExecutionResult(
            execution_id=exec_id,
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            status=WorkflowStatus.SUCCESS,
            step_records=step_records,
            variables_used=variables,
            duration_seconds=time.monotonic() - start_time,
        )

    async def _execute_step(
        self,
        step: VisualWorkflowStep,
        variables: dict[str, str],
        previous_record: StepExecutionRecord | None = None,
        mock_pre_elements: list[dict[str, Any]] | None = None,
    ) -> StepExecutionRecord:
        """Execute a single step with condition evaluation, retries, and verification."""
        step_start = time.monotonic()
        target_query = self._interpolate_variables(step.target_query, variables)
        input_text = self._interpolate_variables(step.input_text, variables)

        retries_taken = 0
        last_error: str | None = None
        last_coords: tuple[int, int] | None = None
        pre_capture_path: str | None = None
        post_capture_path: str | None = None

        for attempt in range(max(1, step.max_retries + 1)):
            retries_taken = attempt

            # 1. Screen Capture & Analysis
            pre_cap = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))
            pre_capture_path = pre_cap.image_path
            analysis = await self._analyzer.analyze_screen(
                image_path=pre_cap.image_path,
                mock_elements=mock_pre_elements,
            )

            # 2. Evaluate Condition (if any)
            if step.condition:
                cond_passed = self._conditions.evaluate(step.condition, analysis, previous_record)
                if not cond_passed:
                    # Skip step or mark conditional success
                    return StepExecutionRecord(
                        step_id=step.step_id,
                        step_name=step.name,
                        action_type=step.action_type,
                        target_label=target_query,
                        grounded_coordinates=None,
                        executed=True,
                        verification_status=VerificationStatus.SUCCESS,
                        error_message="Condition not met; step skipped safely.",
                        retries_taken=retries_taken,
                        pre_capture_path=pre_capture_path,
                        duration_seconds=time.monotonic() - step_start,
                    )

            # 3. Ground Coordinates if target_query exists
            coords: tuple[int, int] | None = None
            if target_query:
                grounded = self._grounding.ground(
                    query=target_query,
                    elements=analysis.detected_elements,
                    fallback_coordinates=step.coordinates_hint,
                )
                if grounded.matched_element or grounded.confidence > 0.3:
                    coords = grounded.target_coordinates
                elif step.coordinates_hint:
                    coords = step.coordinates_hint

                if not coords and step.action_type in {
                    VisualActionType.CLICK,
                    VisualActionType.DOUBLE_CLICK,
                    VisualActionType.RIGHT_CLICK,
                }:
                    last_error = f"Could not visually ground target '{target_query}'."
                    continue  # Retry

            last_coords = coords

            # 4. Permission Gate Check
            if self._gate:
                tool_to_check = self._keyboard if step.action_type in {VisualActionType.TYPE, VisualActionType.KEY_PRESS} else self._mouse
                try:
                    await self._gate.check(tool_to_check)
                except PermissionDeniedError as pe:
                    return StepExecutionRecord(
                        step_id=step.step_id,
                        step_name=step.name,
                        action_type=step.action_type,
                        target_label=target_query,
                        grounded_coordinates=coords,
                        executed=False,
                        verification_status=VerificationStatus.FAILED,
                        error_message=f"Permission denied: {str(pe)}",
                        retries_taken=retries_taken,
                        pre_capture_path=pre_capture_path,
                        duration_seconds=time.monotonic() - step_start,
                    )

            # 5. Execute Action
            exec_ok = await self._dispatch_action(step, coords, input_text)
            if not exec_ok:
                last_error = f"Failed to execute action {step.action_type.value}"
                continue

            # 6. Post-Action Capture & Verification
            post_cap = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))
            post_capture_path = post_cap.image_path

            post_analysis = await self._analyzer.analyze_screen(
                image_path=post_cap.image_path,
                mock_elements=mock_pre_elements,
            )

            # Verify step
            verif_status = self._verify_step(step, post_analysis)
            if verif_status in {VerificationStatus.SUCCESS, VerificationStatus.INDETERMINATE}:
                return StepExecutionRecord(
                    step_id=step.step_id,
                    step_name=step.name,
                    action_type=step.action_type,
                    target_label=target_query,
                    grounded_coordinates=coords,
                    executed=True,
                    verification_status=verif_status,
                    retries_taken=retries_taken,
                    pre_capture_path=pre_capture_path,
                    post_capture_path=post_capture_path,
                    duration_seconds=time.monotonic() - step_start,
                )
            else:
                last_error = f"Post-action verification failed for '{step.name}'."

        # All retries exhausted
        return StepExecutionRecord(
            step_id=step.step_id,
            step_name=step.name,
            action_type=step.action_type,
            target_label=target_query,
            grounded_coordinates=last_coords,
            executed=False,
            verification_status=VerificationStatus.FAILED,
            error_message=last_error or "Step failed after all retries.",
            retries_taken=retries_taken,
            pre_capture_path=pre_capture_path,
            post_capture_path=post_capture_path,
            duration_seconds=time.monotonic() - step_start,
        )

    async def _dispatch_action(
        self,
        step: VisualWorkflowStep,
        coords: tuple[int, int] | None,
        input_text: str,
    ) -> bool:
        """Dispatch concrete mouse, keyboard, or window tool action."""
        x = coords[0] if coords else 0
        y = coords[1] if coords else 0

        match step.action_type:
            case VisualActionType.CLICK:
                res = await self._mouse.execute({"action": "click", "x": x, "y": y, "button": "left"})
                return res.success

            case VisualActionType.DOUBLE_CLICK:
                await self._mouse.execute({"action": "click", "x": x, "y": y, "button": "left"})
                res = await self._mouse.execute({"action": "click", "x": x, "y": y, "button": "left"})
                return res.success

            case VisualActionType.RIGHT_CLICK:
                res = await self._mouse.execute({"action": "click", "x": x, "y": y, "button": "right"})
                return res.success

            case VisualActionType.TYPE:
                if coords:
                    await self._mouse.execute({"action": "click", "x": x, "y": y})
                res = await self._keyboard.execute({"action": "type", "text": input_text})
                return res.success

            case VisualActionType.KEY_PRESS:
                res = await self._keyboard.execute({"action": "press_key", "keys": step.keys})
                return res.success

            case VisualActionType.SCROLL:
                res = await self._mouse.execute({"action": "scroll", "x": x, "y": y, "scroll_amount": step.scroll_delta})
                return res.success

            case VisualActionType.WINDOW_SWITCH:
                if step.window_identifier:
                    res = await self._window.execute({"action": "focus", "window_id": step.window_identifier})
                    return res.success
                return True

            case VisualActionType.WAIT:
                await asyncio.sleep(min(step.wait_duration_seconds, 1.0))
                return True

            case _:
                return True

    def _verify_step(self, step: VisualWorkflowStep, post_analysis: Any) -> VerificationStatus:
        """Evaluate post-action visual verification rules."""
        if not step.verification:
            return VerificationStatus.INDETERMINATE

        v = step.verification
        if v.expected_element:
            found = any(v.expected_element.lower() in el.label.lower() for el in post_analysis.detected_elements)
            if not found:
                return VerificationStatus.FAILED

        if v.expected_text:
            text_corpus = " ".join(post_analysis.detected_text).lower() + " " + post_analysis.summary.lower()
            if v.expected_text.lower() not in text_corpus:
                return VerificationStatus.FAILED

        if v.unexpected_element:
            found = any(v.unexpected_element.lower() in el.label.lower() for el in post_analysis.detected_elements)
            if found:
                return VerificationStatus.FAILED

        return VerificationStatus.SUCCESS
