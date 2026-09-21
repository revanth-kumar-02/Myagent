"""
workspace.manager — Workspace & Project Manager (V18)

Manages multi-project workspace state:
  - Project registration, discovery, updates, active project switching, and archiving
  - Activity log tracking (file changes, indexing, tasks, goals, decisions)
  - Deletion safety guards
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from workspace.discovery import ProjectDiscoveryEngine
from workspace.types import (
    ActivityType,
    ProjectActivityEvent,
    ProjectProfile,
    ProjectStatus,
    Workspace,
)

logger = structlog.get_logger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be found."""


class WorkspaceActionError(Exception):
    """Raised when an invalid action is performed on workspace/projects."""


class WorkspaceManager:
    """
    Coordinates multi-project workspaces, profiles, and activity logging.
    """

    def __init__(
        self,
        discovery_engine: ProjectDiscoveryEngine | None = None,
    ) -> None:
        self.discovery_engine = discovery_engine or ProjectDiscoveryEngine()
        self._workspace = Workspace()
        self._projects: dict[uuid.UUID, ProjectProfile] = {}
        self._activity_log: list[ProjectActivityEvent] = []

    def create_project(
        self,
        name: str,
        root_path: str,
        description: str = "",
        auto_discover: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectProfile:
        """Create and register a new project in the workspace."""
        if not name or not name.strip():
            raise WorkspaceActionError("Project name cannot be empty")
        if not root_path or not root_path.strip():
            raise WorkspaceActionError("Project root_path cannot be empty")

        clean_name = name.strip()
        clean_path = root_path.strip()

        # Run automated codebase discovery if requested
        techs: list[str] = []
        entry_points: list[str] = []
        configs: list[str] = []
        docs: list[str] = []
        test_dirs: list[str] = []
        deps_summary: list[str] = []

        if auto_discover:
            try:
                disc = self.discovery_engine.discover(clean_path)
                techs = disc.languages + disc.frameworks
                entry_points = disc.entry_points
                configs = disc.config_files
                docs = disc.doc_files
                test_dirs = disc.test_structure
                deps_summary = disc.dependencies
            except Exception as e:
                logger.warning("initial_discovery_partial_failure", path=clean_path, error=str(e))

        project = ProjectProfile(
            name=clean_name,
            root_path=clean_path,
            description=description.strip(),
            technologies=techs,
            entry_points=entry_points,
            dependencies_summary=deps_summary,
            config_files=configs,
            doc_files=docs,
            test_dirs=test_dirs,
            metadata=metadata or {},
        )

        self._projects[project.project_id] = project

        # Set as active if first project
        if self._workspace.active_project_id is None:
            self._workspace.active_project_id = project.project_id

        self.record_activity(
            project_id=project.project_id,
            activity_type=ActivityType.FILE_CHANGE,
            title="Project Registered",
            description=f"Project '{project.name}' initialized at {project.root_path}.",
        )

        logger.info("project_registered", project_id=str(project.project_id), name=project.name)
        return project

    def get_project(self, project_id: uuid.UUID | str) -> ProjectProfile | None:
        """Retrieve project by ID."""
        key = uuid.UUID(str(project_id))
        return self._projects.get(key)

    def list_projects(self, status: ProjectStatus | None = None) -> list[ProjectProfile]:
        """List registered projects matching optional status filter."""
        res = list(self._projects.values())
        if status is not None:
            res = [p for p in res if p.status == status]
        return sorted(res, key=lambda x: x.created_at, reverse=True)

    def set_active_project(self, project_id: uuid.UUID | str) -> ProjectProfile:
        """Switch active workspace project."""
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        self._workspace.active_project_id = project.project_id
        self._workspace.updated_at = datetime.now(timezone.utc)
        logger.info("active_project_switched", project_id=str(project.project_id), name=project.name)
        return project

    def get_active_project(self) -> ProjectProfile | None:
        """Get currently active project."""
        if self._workspace.active_project_id:
            return self.get_project(self._workspace.active_project_id)
        return None

    def archive_project(self, project_id: uuid.UUID | str) -> ProjectProfile:
        """Archive a project."""
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        project.status = ProjectStatus.ARCHIVED
        project.updated_at = datetime.now(timezone.utc)

        # Clear active project if archived
        if self._workspace.active_project_id == project.project_id:
            self._workspace.active_project_id = None

        self.record_activity(
            project_id=project.project_id,
            activity_type=ActivityType.FILE_CHANGE,
            title="Project Archived",
            description=f"Project '{project.name}' moved to archive.",
        )
        return project

    def delete_project(self, project_id: uuid.UUID | str, confirm: bool = False) -> bool:
        """Delete project profile with safety confirmation guard."""
        if not confirm:
            raise WorkspaceActionError("Project deletion requires explicit confirm=True")

        key = uuid.UUID(str(project_id))
        if key in self._projects:
            del self._projects[key]
            if self._workspace.active_project_id == key:
                self._workspace.active_project_id = None
            logger.info("project_deleted", project_id=str(key))
            return True
        return False

    def record_activity(
        self,
        project_id: uuid.UUID | str,
        activity_type: ActivityType,
        title: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProjectActivityEvent:
        """Record an activity event for a project."""
        p_key = uuid.UUID(str(project_id))
        event = ProjectActivityEvent(
            project_id=p_key,
            activity_type=activity_type,
            title=title.strip(),
            description=description.strip(),
            metadata=metadata or {},
        )
        self._activity_log.append(event)
        return event

    def list_activity(
        self,
        project_id: uuid.UUID | str | None = None,
        activity_type: ActivityType | None = None,
        limit: int = 50,
    ) -> list[ProjectActivityEvent]:
        """Query activity stream with optional filters."""
        p_key = uuid.UUID(str(project_id)) if project_id else None
        results: list[ProjectActivityEvent] = []

        for evt in sorted(self._activity_log, key=lambda e: e.timestamp, reverse=True):
            if p_key is not None and evt.project_id != p_key:
                continue
            if activity_type is not None and evt.activity_type != activity_type:
                continue
            results.append(evt)
            if len(results) >= limit:
                break

        return results
