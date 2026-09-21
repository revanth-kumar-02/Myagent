"""
workspace.proactive_hooks — Workspace Proactive Intelligence Detector (V18)

Monitors workspace projects and health indicators to generate proactive suggestions
via Kora's Proactive Intelligence Engine:
  - Suggesting search indexing for newly registered or unindexed codebases
  - Alerting on elevated task failure rates in active projects
"""

from __future__ import annotations

from proactive.detector import EventDetector
from proactive.types import EventSourceType, EventUrgency, ProactiveEvent
from workspace.health import ProjectHealthEngine
from workspace.manager import WorkspaceManager


class WorkspaceProactiveDetector:
    """
    Scans workspace projects and dispatches proactive health events.
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager | None = None,
        health_engine: ProjectHealthEngine | None = None,
        detector: EventDetector | None = None,
    ) -> None:
        self.workspace_mgr = workspace_manager or WorkspaceManager()
        self.health_engine = health_engine or ProjectHealthEngine()
        self.detector = detector or EventDetector()

    async def scan_workspace_health(self) -> list[ProactiveEvent]:
        """Scan all projects in workspace and emit proactive events if health needs attention."""
        emitted: list[ProactiveEvent] = []

        for project in self.workspace_mgr.list_projects():
            health = self.health_engine.compute_health(
                project=project,
                total_files=len(project.config_files) + len(project.doc_files) + len(project.entry_points),
            )

            # Unindexed project suggestion
            if health.indexing_status.value == "not_indexed" and len(project.entry_points) > 0:
                evt = ProactiveEvent(
                    source_type=EventSourceType.PROJECT_FILE_CHANGE,
                    title=f"Unindexed Project: {project.name}",
                    description=f"Project '{project.name}' has source code but no search index. Re-indexing is recommended.",
                    project_id=project.project_id,
                    urgency=EventUrgency.NORMAL,
                    importance=0.7,
                    data={
                        "event_subtype": "unindexed_project",
                        "project_id": str(project.project_id),
                        "project_name": project.name,
                    },
                )
                res = await self.detector.emit(evt)
                emitted.append(res)

        return emitted
