"""
workspace.health — Factual Project Health Engine (V18)

Derives real-time project health indicators from concrete system states:
  - RAG Indexing status and total chunk counts
  - Autonomous task breakdown (active, completed, failed)
  - Goal progression and active/completed counts
  - Documentation file coverage ratio
  - Actionable issue diagnostics (zero invented metrics)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

import structlog

from personal.types import GoalState
from tasks.types import TaskState
from workspace.types import (
    IndexingStatus,
    ProjectHealth,
    ProjectHealthStatus,
    ProjectProfile,
)

logger = structlog.get_logger(__name__)


class ProjectHealthEngine:
    """
    Computes factual project indicators from concrete workspace components.
    """

    def compute_health(
        self,
        project: ProjectProfile,
        total_files: int = 0,
        total_chunks: int = 0,
        is_indexing: bool = False,
        tasks: Sequence[Any] | None = None,
        goals: Sequence[Any] | None = None,
        last_activity_at: datetime | None = None,
    ) -> ProjectHealth:
        """
        Evaluate project health strictly from factual inputs.
        """
        issues: list[str] = []

        # 1. Indexing Status
        if is_indexing:
            idx_status = IndexingStatus.IN_PROGRESS
        elif total_chunks > 0:
            idx_status = IndexingStatus.INDEXED
        else:
            idx_status = IndexingStatus.NOT_INDEXED
            if total_files > 5:
                issues.append(f"Project has {total_files} files but search index is not built.")

        # 2. Tasks Breakdown
        all_tasks = tasks or []
        active_tasks = [t for t in all_tasks if getattr(t, "status", None) in (TaskState.PENDING, TaskState.RUNNING)]
        failed_tasks = [t for t in all_tasks if getattr(t, "status", None) in (TaskState.FAILED, "failed")]

        if failed_tasks:
            issues.append(f"{len(failed_tasks)} failed task(s) require attention.")

        # 3. Goals Breakdown
        all_goals = goals or []
        active_goals = [g for g in all_goals if getattr(g, "state", None) == GoalState.ACTIVE]
        completed_goals = [g for g in all_goals if getattr(g, "state", None) == GoalState.COMPLETED]

        # 4. Documentation Coverage
        doc_count = len(project.doc_files)
        total_ref = max(1, total_files or len(project.config_files) + len(project.entry_points) + doc_count)
        doc_ratio = round(min(1.0, doc_count / total_ref), 2)
        if doc_count == 0 and total_files > 3:
            issues.append("No documentation files (README/docs) found.")

        # 5. Overall Health Classification
        if failed_tasks and len(failed_tasks) > len(active_tasks) + 1:
            health_status = ProjectHealthStatus.DEGRADED
        elif issues:
            health_status = ProjectHealthStatus.NEEDS_ATTENTION
        elif idx_status == IndexingStatus.INDEXED:
            health_status = ProjectHealthStatus.HEALTHY
        else:
            health_status = ProjectHealthStatus.HEALTHY if total_files <= 5 else ProjectHealthStatus.NEEDS_ATTENTION

        return ProjectHealth(
            indexing_status=idx_status,
            total_files=total_files,
            total_chunks=total_chunks,
            active_tasks_count=len(active_tasks),
            failed_tasks_count=len(failed_tasks),
            active_goals_count=len(active_goals),
            completed_goals_count=len(completed_goals),
            doc_coverage_ratio=doc_ratio,
            health_status=health_status,
            issues=issues,
            last_activity_at=last_activity_at or datetime.now(timezone.utc),
        )
