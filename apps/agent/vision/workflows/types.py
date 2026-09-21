"""
vision.workflows.types — Domain Types for Visual Workflow Automation (V20)

Defines visual actions, conditions, verification criteria, workflow steps,
workflows, execution logs, and replay models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from vision.types import VerificationStatus


class VisualActionType(str, Enum):
    """Types of visual actions supported in workflows."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEY_PRESS = "key_press"
    SCROLL = "scroll"
    DRAG = "drag"
    SELECT = "select"
    WAIT = "wait"
    WINDOW_SWITCH = "window_switch"


class ConditionType(str, Enum):
    """Types of conditions evaluated before executing a step."""
    ELEMENT_EXISTS = "element_exists"
    TEXT_APPEARS = "text_appears"
    DIALOG_APPEARS = "dialog_appears"
    SCREEN_STATE_MATCHES = "screen_state_matches"
    PREVIOUS_ACTION_SUCCEEDED = "previous_action_succeeded"


class WorkflowStatus(str, Enum):
    """Overall workflow execution state."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class VisualStepCondition:
    """Pre-condition to evaluate before step execution."""
    condition_type: ConditionType
    target_label: str | None = None
    expected_text: str | None = None
    timeout_seconds: float = 5.0
    negate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_type": self.condition_type.value,
            "target_label": self.target_label,
            "expected_text": self.expected_text,
            "timeout_seconds": self.timeout_seconds,
            "negate": self.negate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualStepCondition:
        return cls(
            condition_type=ConditionType(data["condition_type"]),
            target_label=data.get("target_label"),
            expected_text=data.get("expected_text"),
            timeout_seconds=float(data.get("timeout_seconds", 5.0)),
            negate=bool(data.get("negate", False)),
        )


@dataclass
class VisualStepVerification:
    """Post-action verification criteria."""
    expected_element: str | None = None
    expected_text: str | None = None
    unexpected_element: str | None = None
    timeout_seconds: float = 5.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_element": self.expected_element,
            "expected_text": self.expected_text,
            "unexpected_element": self.unexpected_element,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualStepVerification:
        return cls(
            expected_element=data.get("expected_element"),
            expected_text=data.get("expected_text"),
            unexpected_element=data.get("unexpected_element"),
            timeout_seconds=float(data.get("timeout_seconds", 5.0)),
        )


@dataclass
class VisualWorkflowStep:
    """Single step in a visual workflow."""
    step_id: str
    name: str
    action_type: VisualActionType
    target_query: str | None = None
    input_text: str | None = None
    keys: list[str] = field(default_factory=list)
    scroll_delta: int = 0
    window_identifier: str | None = None
    coordinates_hint: tuple[int, int] | None = None
    condition: VisualStepCondition | None = None
    verification: VisualStepVerification | None = None
    max_retries: int = 2
    wait_duration_seconds: float = 0.5
    on_failure_branch_to_step: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "action_type": self.action_type.value,
            "target_query": self.target_query,
            "input_text": self.input_text,
            "keys": self.keys,
            "scroll_delta": self.scroll_delta,
            "window_identifier": self.window_identifier,
            "coordinates_hint": list(self.coordinates_hint) if self.coordinates_hint else None,
            "condition": self.condition.to_dict() if self.condition else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "max_retries": self.max_retries,
            "wait_duration_seconds": self.wait_duration_seconds,
            "on_failure_branch_to_step": self.on_failure_branch_to_step,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualWorkflowStep:
        return cls(
            step_id=data["step_id"],
            name=data["name"],
            action_type=VisualActionType(data["action_type"]),
            target_query=data.get("target_query"),
            input_text=data.get("input_text"),
            keys=data.get("keys", []),
            scroll_delta=int(data.get("scroll_delta", 0)),
            window_identifier=data.get("window_identifier"),
            coordinates_hint=tuple(data["coordinates_hint"]) if data.get("coordinates_hint") else None,
            condition=VisualStepCondition.from_dict(data["condition"]) if data.get("condition") else None,
            verification=VisualStepVerification.from_dict(data["verification"]) if data.get("verification") else None,
            max_retries=int(data.get("max_retries", 2)),
            wait_duration_seconds=float(data.get("wait_duration_seconds", 0.5)),
            on_failure_branch_to_step=data.get("on_failure_branch_to_step"),
        )


@dataclass
class VisualWorkflow:
    """Complete visual workflow specification."""
    workflow_id: str
    name: str
    description: str
    target_app: str | None = None
    variables: dict[str, str] = field(default_factory=dict)
    steps: list[VisualWorkflowStep] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "target_app": self.target_app,
            "variables": self.variables,
            "steps": [s.to_dict() for s in self.steps],
            "required_permissions": self.required_permissions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualWorkflow:
        return cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            description=data.get("description", ""),
            target_app=data.get("target_app"),
            variables=data.get("variables", {}),
            steps=[VisualWorkflowStep.from_dict(s) for s in data.get("steps", [])],
            required_permissions=data.get("required_permissions", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc),
        )


@dataclass
class StepExecutionRecord:
    """Execution record for an individual workflow step."""
    step_id: str
    step_name: str
    action_type: VisualActionType
    target_label: str | None
    grounded_coordinates: tuple[int, int] | None
    executed: bool
    verification_status: VerificationStatus
    error_message: str | None = None
    retries_taken: int = 0
    pre_capture_path: str | None = None
    post_capture_path: str | None = None
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "action_type": self.action_type.value,
            "target_label": self.target_label,
            "grounded_coordinates": list(self.grounded_coordinates) if self.grounded_coordinates else None,
            "executed": self.executed,
            "verification_status": self.verification_status.value,
            "error_message": self.error_message,
            "retries_taken": self.retries_taken,
            "pre_capture_path": self.pre_capture_path,
            "post_capture_path": self.post_capture_path,
            "duration_seconds": round(self.duration_seconds, 3),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WorkflowExecutionResult:
    """Final output of executing a visual workflow."""
    execution_id: str
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    step_records: list[StepExecutionRecord] = field(default_factory=list)
    variables_used: dict[str, str] = field(default_factory=dict)
    error_message: str | None = None
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "step_records": [s.to_dict() for s in self.step_records],
            "variables_used": self.variables_used,
            "error_message": self.error_message,
            "duration_seconds": round(self.duration_seconds, 3),
            "timestamp": self.timestamp.isoformat(),
        }
