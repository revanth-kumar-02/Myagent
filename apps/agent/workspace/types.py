"""
workspace.types — Data Types, Schemas, and Enums for Kora Workspace & Project Intelligence (V18).

Defines:
  - Project statuses, indexing states, and health indicators
  - Codebase discovery models (languages, frameworks, configs, entry points)
  - Factual project health indicators and activity streams
  - Unified project context with multi-project isolation
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ProjectStatus(str, enum.Enum):
    """Operational status of a project in the workspace."""
    ACTIVE   = "active"
    INDEXING = "indexing"
    ARCHIVED = "archived"
    PAUSED   = "paused"


class IndexingStatus(str, enum.Enum):
    """RAG indexing state for a project."""
    NOT_INDEXED = "not_indexed"
    IN_PROGRESS = "in_progress"
    INDEXED     = "indexed"
    ERROR       = "error"


class ProjectHealthStatus(str, enum.Enum):
    """Overall factual health state of a project."""
    HEALTHY         = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    DEGRADED        = "degraded"
    UNKNOWN         = "unknown"


class ActivityType(str, enum.Enum):
    """Category of project activity event."""
    FILE_CHANGE = "file_change"
    INDEXING    = "indexing"
    TASK        = "task"
    GOAL        = "goal"
    DECISION    = "decision"
    RESEARCH    = "research"
    AGENT_TURN  = "agent_turn"


@dataclass
class ProjectDiscoveryResult:
    """Automated codebase discovery findings."""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    important_directories: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    doc_files: list[str] = field(default_factory=list)
    db_configs: list[str] = field(default_factory=list)
    test_structure: list[str] = field(default_factory=list)


@dataclass
class ProjectProfile:
    """Unified profile representing a project."""
    name: str
    root_path: str
    project_id: uuid.UUID = field(default_factory=uuid.uuid4)
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    technologies: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dependencies_summary: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    doc_files: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = ProjectStatus(self.status)


@dataclass
class ProjectHealth:
    """Factual project health indicators calculated from real state."""
    indexing_status: IndexingStatus = IndexingStatus.NOT_INDEXED
    total_files: int = 0
    total_chunks: int = 0
    active_tasks_count: int = 0
    failed_tasks_count: int = 0
    active_goals_count: int = 0
    completed_goals_count: int = 0
    doc_coverage_ratio: float = 0.0  # 0.0 to 1.0 (docs / total files)
    health_status: ProjectHealthStatus = ProjectHealthStatus.UNKNOWN
    issues: list[str] = field(default_factory=list)
    last_activity_at: datetime | None = None


@dataclass
class ProjectActivityEvent:
    """Historical activity event logged within a project context."""
    project_id: uuid.UUID
    activity_type: ActivityType
    title: str
    description: str = ""
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.activity_type, str):
            self.activity_type = ActivityType(self.activity_type)


@dataclass
class UnifiedProjectContext:
    """Complete project context package assembled for the Agent Core."""
    project_profile: ProjectProfile
    discovery: ProjectDiscoveryResult
    health: ProjectHealth
    active_goals: list[Any] = field(default_factory=list)
    recent_decisions: list[Any] = field(default_factory=list)
    active_tasks: list[Any] = field(default_factory=list)
    recent_memories: list[Any] = field(default_factory=list)
    rag_summary: str = ""
    knowledge_graph_summary: str = ""
    summary_text: str = ""
    token_count: int = 0


@dataclass
class Workspace:
    """Top-level workspace container managing multiple projects."""
    name: str = "Default Workspace"
    workspace_id: uuid.UUID = field(default_factory=uuid.uuid4)
    active_project_id: uuid.UUID | None = None
    projects: list[ProjectProfile] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
