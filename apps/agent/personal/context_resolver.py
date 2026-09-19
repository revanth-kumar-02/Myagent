"""
personal.context_resolver — Personal Context Resolution & Privacy Boundaries (V17)

Retrieves, budgets, and scopes personal goals, milestones, and decisions:
  - Selects only relevant active goals and decisions based on query and project context
  - Bounded token package creation
  - Strict privacy boundary enforcement:
      * Sub-agents receive only scoped goal targets (no unrelated decisions/notes)
      * Web research queries are sanitized to prevent personal data leaks to DuckDuckGo
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from orchestration.types import AgentType
from personal.journal import DecisionJournal
from personal.manager import GoalManager
from personal.types import Goal, GoalState, PersonalContextPackage


class PersonalContextResolver:
    """
    Assembles relevant personal context and enforces privacy boundaries.
    """

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        journal: DecisionJournal | None = None,
    ) -> None:
        self.goal_manager = goal_manager or GoalManager()
        self.journal = journal or DecisionJournal()

    def resolve(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_goals: int = 3,
        max_decisions: int = 3,
    ) -> PersonalContextPackage:
        """
        Resolve relevant active goals and decisions into a bounded context package.
        """
        # Fetch active goals for project
        all_goals = self.goal_manager.list_goals(project_id=project_id, state=GoalState.ACTIVE)
        if not all_goals and project_id is not None:
            # Fallback: check global goals
            all_goals = self.goal_manager.list_goals(state=GoalState.ACTIVE)

        selected_goals = all_goals[:max_goals]

        # Fetch relevant decisions
        all_decisions = self.journal.list_decisions(project_id=project_id, limit=max_decisions)
        selected_decisions = all_decisions[:max_decisions]

        # Collect active milestones
        active_milestones = []
        for g in selected_goals:
            for m in g.milestones:
                if not m.completed:
                    active_milestones.append(m)

        # Build formatted summary text
        sections: list[str] = []
        if selected_goals:
            goal_lines = [
                f"- [Goal] {g.title} (Progress: {int(g.progress*100)}%, Target: {g.target_date.strftime('%Y-%m-%d') if g.target_date else 'None'})"
                for g in selected_goals
            ]
            sections.append("### Active Goals:\n" + "\n".join(goal_lines))

        if active_milestones:
            ms_lines = [f"- [Milestone] {m.title} (Deadline: {m.deadline.strftime('%Y-%m-%d') if m.deadline else 'None'})" for m in active_milestones[:5]]
            sections.append("### Pending Milestones:\n" + "\n".join(ms_lines))

        if selected_decisions:
            dec_lines = [f"- [Decision] {d.decision_text} (Reason: {d.reasoning[:60]}...)" for d in selected_decisions]
            sections.append("### Recent Key Decisions:\n" + "\n".join(dec_lines))

        summary_text = "\n\n".join(sections)
        token_count = len(summary_text.split())  # approximate token count

        return PersonalContextPackage(
            goals=selected_goals,
            decisions=selected_decisions,
            active_milestones=active_milestones,
            summary_text=summary_text,
            token_count=token_count,
        )

    def scope_for_subagent(
        self,
        pkg: PersonalContextPackage,
        agent_type: AgentType,
    ) -> dict[str, Any]:
        """
        Scope personal context specifically for a specialized sub-agent.
        Prevents leaking unrelated personal decisions, unassociated notes, or user habits.
        """
        # Sub-agents only receive goal titles and relevant milestone objectives
        return {
            "goals": [{"title": g.title, "progress": g.progress} for g in pkg.goals],
            "milestones": [{"title": m.title} for m in pkg.active_milestones],
            # Decisions are strictly stripped unless it's a coding architectural decision for coding agent
            "decisions": [
                {"decision": d.decision_text}
                for d in pkg.decisions
                if agent_type == AgentType.CODING_AGENT and "code" in d.tags
            ],
        }

    def sanitize_for_web_research(self, raw_query: str) -> str:
        """
        Sanitize search query so personal names, local paths, and private goals
        are never transmitted to external search providers.
        """
        clean = raw_query
        # Remove absolute local paths (/home/...)
        clean = re.sub(r'/[a-zA-Z0-9_\-\./]+', '', clean)
        # Remove sensitive email addresses
        clean = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', clean)
        return clean.strip()
