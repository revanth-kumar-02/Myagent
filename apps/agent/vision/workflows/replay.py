"""
vision.workflows.replay — Visual Workflow Replayer (V20)

Replays saved workflows using dynamic visual grounding and parameter interpolation.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import structlog

from vision.workflows.engine import VisualWorkflowEngine
from vision.workflows.types import VisualWorkflow, WorkflowExecutionResult

logger = structlog.get_logger(__name__)


class VisualWorkflowReplayer:
    """
    Manages loading, parameterizing, and replaying visual workflows.
    """

    def __init__(self, engine: VisualWorkflowEngine | None = None) -> None:
        self._engine = engine or VisualWorkflowEngine()

    @classmethod
    def load_from_file(cls, file_path: str) -> VisualWorkflow:
        """Load a VisualWorkflow specification from a JSON file."""
        path = pathlib.Path(file_path)
        data = json.loads(path.read_text())
        return VisualWorkflow.from_dict(data)

    async def replay(
        self,
        workflow: VisualWorkflow | str,
        runtime_variables: dict[str, str] | None = None,
        mock_pre_elements: list[dict[str, Any]] | None = None,
    ) -> WorkflowExecutionResult:
        """
        Replay a workflow (from VisualWorkflow instance or file path).
        """
        if isinstance(workflow, str):
            wf = self.load_from_file(workflow)
        else:
            wf = workflow

        logger.info("replaying_visual_workflow", workflow_name=wf.name, variables=runtime_variables)
        return await self._engine.execute_workflow(
            workflow=wf,
            runtime_variables=runtime_variables,
            mock_pre_elements=mock_pre_elements,
        )
