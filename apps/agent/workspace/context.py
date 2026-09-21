"""
workspace.context — Unified Project Context & Multi-Project Isolation (V18)

Assembles comprehensive project context for Kora's Agent Core:
  - Project Profile & Discovery Metadata
  - Factual Health & Real-time Task Breakdown
  - Project-Scoped Goals, Milestones, and Decisions
  - Project-Isolated RAG index and Knowledge Graph entities

Enforces strict multi-project boundary isolation (zero cross-project leakage).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from personal.journal import DecisionJournal
from personal.manager import GoalManager
from personal.types import GoalState
from tasks.manager import TaskManager
from workspace.discovery import ProjectDiscoveryEngine
from workspace.health import ProjectHealthEngine
from workspace.manager import WorkspaceManager
from workspace.types import UnifiedProjectContext

logger = structlog.get_logger(__name__)


class ProjectContextBuilder:
    """
    Builds structured, project-scoped unified context while guaranteeing multi-project isolation.
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager | None = None,
        discovery_engine: ProjectDiscoveryEngine | None = None,
        health_engine: ProjectHealthEngine | None = None,
        goal_manager: GoalManager | None = None,
        journal: DecisionJournal | None = None,
        task_manager: TaskManager | None = None,
        memory_manager: Any | None = None,
        graph_store: Any | None = None,
    ) -> None:
        self.workspace_mgr = workspace_manager or WorkspaceManager()
        self.discovery_engine = discovery_engine or ProjectDiscoveryEngine()
        self.health_engine = health_engine or ProjectHealthEngine()
        self.goal_mgr = goal_manager or GoalManager()
        self.journal = journal or DecisionJournal()
        self.task_mgr = task_manager
        self.memory_mgr = memory_manager
        self.graph_store = graph_store

    async def build_project_context(
        self,
        project_id: uuid.UUID | str,
        total_files: int = 0,
        total_chunks: int = 0,
        max_tokens: int = 2000,
    ) -> UnifiedProjectContext:
        """
        Assemble unified context for a project with strict isolation.
        """
        p_key = uuid.UUID(str(project_id))
        project = self.workspace_mgr.get_project(p_key)
        if not project:
            raise ValueError(f"Project {project_id} not found in workspace")

        # 1. Discovery
        disc = self.discovery_engine.discover(project.root_path)

        # 2. Strict Project-Isolated Goals
        project_goals = self.goal_mgr.list_goals(project_id=p_key, state=GoalState.ACTIVE)

        # 3. Strict Project-Isolated Decisions
        project_decisions = self.journal.list_decisions(project_id=p_key, limit=5)

        # 4. Strict Project-Isolated Tasks
        project_tasks = []
        if self.task_mgr:
            try:
                project_tasks = await self.task_mgr.list_tasks(project_id=p_key)
            except Exception as e:
                logger.warning("task_context_fetch_failed", project_id=str(p_key), error=str(e))

        # 5. Project Health
        health = self.health_engine.compute_health(
            project=project,
            total_files=total_files,
            total_chunks=total_chunks,
            tasks=project_tasks,
            goals=project_goals,
        )

        # 6. Strict Project-Isolated Memories
        recent_memories = []
        if self.memory_mgr:
            try:
                recent_memories = await self.memory_mgr.retrieve_memories(
                    query=project.name,
                    project_id=p_key,
                    top_k=4,
                )
            except Exception:
                pass

        # Format Summary Text
        sections: list[str] = [
            f"## Project Context: {project.name}",
            f"- **Root Path**: `{project.root_path}`",
            f"- **Status**: {project.status.value.upper()} | **Health**: {health.health_status.value.upper()}",
            f"- **Technologies**: {', '.join(project.technologies) if project.technologies else 'None detected'}",
        ]

        if project.entry_points:
            sections.append(f"- **Entry Points**: {', '.join(project.entry_points[:4])}")

        if project_goals:
            goal_bullets = [f"  * {g.title} ({int(g.progress*100)}% complete)" for g in project_goals[:4]]
            sections.append("- **Active Goals**:\n" + "\n".join(goal_bullets))

        if project_decisions:
            dec_bullets = [f"  * {d.decision_text} ({d.reasoning[:50]}...)" for d in project_decisions[:3]]
            sections.append("- **Recent Key Decisions**:\n" + "\n".join(dec_bullets))

        if health.issues:
            sections.append(f"- **Health Alerts**: {'; '.join(health.issues)}")

        summary_text = "\n".join(sections)
        token_count = len(summary_text.split())

        return UnifiedProjectContext(
            project_profile=project,
            discovery=disc,
            health=health,
            active_goals=project_goals,
            recent_decisions=project_decisions,
            active_tasks=project_tasks,
            recent_memories=recent_memories,
            rag_summary=f"Indexed Chunks: {total_chunks} across {total_files} files." if total_chunks > 0 else "Unindexed",
            summary_text=summary_text,
            token_count=token_count,
        )

    def detect_project_from_query(self, query: str) -> uuid.UUID | None:
        """Match query terms against registered projects."""
        clean = query.lower()
        for project in self.workspace_mgr.list_projects():
            if project.name.lower() in clean or project.root_path.lower() in clean:
                return project.project_id
        return None
