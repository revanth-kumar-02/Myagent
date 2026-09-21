"""
vision.workflows.recorder — Visual Workflow Recorder (V20)

Records user or agent visual actions into structured, privacy-safe workflows.
"""

from __future__ import annotations

import json
import pathlib
import re
import uuid
from typing import Any

import structlog

from vision.workflows.types import (
    VisualActionType,
    VisualStepCondition,
    VisualStepVerification,
    VisualWorkflow,
    VisualWorkflowStep,
)

logger = structlog.get_logger(__name__)

# Secret sanitization pattern to ensure private credentials on screen are never stored
_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key|bearer)[\s:=]+['\"]?([^\s'\"]+)"),
    re.compile(r"ghp_[A-Za-z0-9_]{36}"),
    re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
]


class VisualWorkflowRecorder:
    """
    Constructs and persists reusable visual workflows with secret masking.
    """

    def __init__(self, name: str, description: str = "", target_app: str | None = None) -> None:
        self.workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.target_app = target_app
        self.steps: list[VisualWorkflowStep] = []
        self.variables: dict[str, str] = {}
        self.required_permissions: list[str] = []

    def _sanitize(self, text: str | None) -> str | None:
        """Mask potential credentials or passwords."""
        if not text:
            return text
        sanitized = text
        for pat in _SENSITIVE_PATTERNS:
            sanitized = pat.sub(r"[REDACTED_SECRET]", sanitized)
        return sanitized

    def set_variable(self, name: str, default_value: str) -> None:
        """Register a workflow variable (rejects secret keys)."""
        clean_name = name.strip()
        if any(sec in clean_name.lower() for sec in ["password", "token", "secret", "api_key"]):
            logger.warning("rejected_sensitive_workflow_variable", variable_name=clean_name)
            return
        self.variables[clean_name] = default_value

    def add_click(
        self,
        name: str,
        target_query: str,
        coordinates_hint: tuple[int, int] | None = None,
        button: str = "left",
        verification: VisualStepVerification | None = None,
    ) -> VisualWorkflowStep:
        """Record a visual click step."""
        action_type = VisualActionType.RIGHT_CLICK if button == "right" else VisualActionType.CLICK
        step = VisualWorkflowStep(
            step_id=f"step_{len(self.steps) + 1}",
            name=name,
            action_type=action_type,
            target_query=self._sanitize(target_query),
            coordinates_hint=coordinates_hint,
            verification=verification,
        )
        self.steps.append(step)
        return step

    def add_type(
        self,
        name: str,
        target_query: str | None,
        input_text: str,
        coordinates_hint: tuple[int, int] | None = None,
        verification: VisualStepVerification | None = None,
    ) -> VisualWorkflowStep:
        """Record a visual typing step with secret masking."""
        step = VisualWorkflowStep(
            step_id=f"step_{len(self.steps) + 1}",
            name=name,
            action_type=VisualActionType.TYPE,
            target_query=self._sanitize(target_query),
            input_text=self._sanitize(input_text),
            coordinates_hint=coordinates_hint,
            verification=verification,
        )
        self.steps.append(step)
        return step

    def add_window_switch(self, name: str, window_identifier: str) -> VisualWorkflowStep:
        """Record a window switch step."""
        step = VisualWorkflowStep(
            step_id=f"step_{len(self.steps) + 1}",
            name=name,
            action_type=VisualActionType.WINDOW_SWITCH,
            window_identifier=window_identifier,
        )
        self.steps.append(step)
        return step

    def add_conditional_step(
        self,
        name: str,
        action_type: VisualActionType,
        condition: VisualStepCondition,
        target_query: str | None = None,
        input_text: str | None = None,
        verification: VisualStepVerification | None = None,
    ) -> VisualWorkflowStep:
        """Record a step guarded by a pre-condition."""
        step = VisualWorkflowStep(
            step_id=f"step_{len(self.steps) + 1}",
            name=name,
            action_type=action_type,
            target_query=self._sanitize(target_query),
            input_text=self._sanitize(input_text),
            condition=condition,
            verification=verification,
        )
        self.steps.append(step)
        return step

    def build_workflow(self) -> VisualWorkflow:
        """Compile recorded steps into a final VisualWorkflow object."""
        return VisualWorkflow(
            workflow_id=self.workflow_id,
            name=self.name,
            description=self.description,
            target_app=self.target_app,
            variables=dict(self.variables),
            steps=list(self.steps),
            required_permissions=list(self.required_permissions),
        )

    def save_to_file(self, file_path: str) -> str:
        """Save workflow definition to a JSON file."""
        wf = self.build_workflow()
        path = pathlib.Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(wf.to_dict(), indent=2))
        return str(path)
