"""
workspace — Kora Workspace & Project Intelligence Subsystem (V18)

Exports:
  - WorkspaceManager, WorkspaceActionError, ProjectNotFoundError
  - ProjectDiscoveryEngine
  - ProjectHealthEngine
  - ProjectContextBuilder
  - WorkspaceProactiveDetector
  - Types, enums, dataclasses, and project profiles
"""

from workspace.context import ProjectContextBuilder
from workspace.discovery import ProjectDiscoveryEngine
from workspace.health import ProjectHealthEngine
from workspace.manager import ProjectNotFoundError, WorkspaceActionError, WorkspaceManager
from workspace.proactive_hooks import WorkspaceProactiveDetector
from workspace.types import (
    ActivityType,
    IndexingStatus,
    ProjectActivityEvent,
    ProjectDiscoveryResult,
    ProjectHealth,
    ProjectHealthStatus,
    ProjectProfile,
    ProjectStatus,
    UnifiedProjectContext,
    Workspace,
)

__all__ = [
    "WorkspaceManager",
    "WorkspaceActionError",
    "ProjectNotFoundError",
    "ProjectDiscoveryEngine",
    "ProjectHealthEngine",
    "ProjectContextBuilder",
    "WorkspaceProactiveDetector",
    "ProjectProfile",
    "ProjectStatus",
    "IndexingStatus",
    "ProjectHealthStatus",
    "ActivityType",
    "ProjectDiscoveryResult",
    "ProjectHealth",
    "ProjectActivityEvent",
    "UnifiedProjectContext",
    "Workspace",
]
