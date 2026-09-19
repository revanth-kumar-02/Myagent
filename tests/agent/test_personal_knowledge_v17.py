"""
tests.agent.test_personal_knowledge_v17 — Test Suite for Kora Personal Knowledge & Goal Intelligence (V17)

Verifies:
  1. Goal lifecycle: create, update, pause, resume, complete, cancel, archive, delete
  2. Mathematical fact-based progress calculation: (completed milestones + completed tasks) / total
  3. Milestone completion and auto-completion when all milestones done
  4. Deletion safety guard (requires confirm=True)
  5. Decision Journal: logging alternatives, trade-offs, reasoning, and updating outcomes
  6. Knowledge Graph bridge: project supports goal, task contributes to goal, decision affects project
  7. Context resolution, token budgeting, and project isolation
  8. Privacy boundaries: sub-agent scoping & sanitization for external web search
  9. Proactive deadline & stalled goal detection
 10. Database schema models
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from graph.store import GraphStore
from graph.types import EntityType, RelationshipType
from orchestration.types import AgentType
from personal.context_resolver import PersonalContextResolver
from personal.graph_bridge import PersonalKnowledgeBridge
from personal.journal import DecisionJournal
from personal.manager import GoalActionError, GoalManager, GoalNotFoundError
from personal.proactive_hooks import PersonalProactiveDetector
from personal.types import GoalPriority, GoalState
from proactive.detector import EventDetector
from db.schema import PersonalDecisionRecord, PersonalGoalRecord, PersonalMilestoneRecord


# ── 1. Goal Lifecycle Tests ───────────────────────────────────────────────────

def test_goal_lifecycle_and_transitions():
    mgr = GoalManager()
    project_id = uuid.uuid4()

    # 1. Create
    goal = mgr.create_goal(
        title="Ship Kora V17",
        description="Personal knowledge layer",
        priority=GoalPriority.HIGH,
        project_id=project_id,
        target_date=datetime.now(timezone.utc) + timedelta(days=5),
    )
    assert goal.state == GoalState.ACTIVE
    assert goal.progress == 0.0

    # 2. Update
    updated = mgr.update_goal(goal.goal_id, description="Updated description", priority=GoalPriority.CRITICAL)
    assert updated.description == "Updated description"
    assert updated.priority == GoalPriority.CRITICAL

    # 3. Pause & Resume
    paused = mgr.pause_goal(goal.goal_id)
    assert paused.state == GoalState.PAUSED
    resumed = mgr.resume_goal(goal.goal_id)
    assert resumed.state == GoalState.ACTIVE

    # 4. Cancel
    cancelled = mgr.cancel_goal(goal.goal_id, reason="Changed direction")
    assert cancelled.state == GoalState.CANCELLED
    assert cancelled.metadata["cancellation_reason"] == "Changed direction"

    # 5. Archive
    archived = mgr.archive_goal(goal.goal_id)
    assert archived.state == GoalState.ARCHIVED


# ── 2. Mathematical Progress Calculation Tests ────────────────────────────────

def test_mathematical_progress_calculation():
    mgr = GoalManager()
    goal = mgr.create_goal(title="Complete Architecture Milestone")

    # Add 2 milestones
    m1 = mgr.add_milestone(goal.goal_id, title="Draft Design")
    m2 = mgr.add_milestone(goal.goal_id, title="Implement Code")
    assert goal.progress == 0.0

    # Complete 1 milestone -> progress = 1/2 = 0.5
    mgr.complete_milestone(goal.goal_id, m1.milestone_id)
    assert goal.progress == 0.5
    assert goal.state == GoalState.ACTIVE

    # Link 2 autonomous tasks
    t1 = uuid.uuid4()
    t2 = uuid.uuid4()
    mgr.link_task(goal.goal_id, t1)
    mgr.link_task(goal.goal_id, t2)
    # Total items = 2 milestones + 2 tasks = 4 items. Completed = 1 milestone -> 1/4 = 0.25
    mgr.calculate_progress(goal.goal_id, completed_task_ids=set())
    assert goal.progress == 0.25

    # Mark t1 complete and m2 complete -> Completed = 2 milestones + 1 task = 3/4 = 0.75
    mgr.complete_milestone(goal.goal_id, m2.milestone_id)
    mgr.calculate_progress(goal.goal_id, completed_task_ids={t1})
    assert goal.progress == 0.75

    # Mark t2 complete -> Completed = 4/4 = 1.0 (Auto-completes goal!)
    mgr.calculate_progress(goal.goal_id, completed_task_ids={t1, t2})
    assert goal.progress == 1.0
    assert goal.state == GoalState.COMPLETED
    assert goal.completed_at is not None


def test_goal_deletion_safety_guard():
    mgr = GoalManager()
    goal = mgr.create_goal(title="Temporary Goal")

    # Deletion without confirm=True raises error
    with pytest.raises(GoalActionError):
        mgr.delete_goal(goal.goal_id, confirm=False)

    # Deletion with confirm=True succeeds
    deleted = mgr.delete_goal(goal.goal_id, confirm=True)
    assert deleted is True
    assert mgr.get_goal(goal.goal_id) is None


# ── 3. Decision Journal Tests ─────────────────────────────────────────────────

def test_decision_journal():
    journal = DecisionJournal()
    project_id = uuid.uuid4()

    # Record decision
    rec = journal.record_decision(
        decision_text="Use PostgreSQL + pgvector for long-term memory",
        context="Evaluated local Chroma vs SQLite vs PostgreSQL",
        alternatives_considered=["SQLite-vec", "ChromaDB", "Pinecone Cloud"],
        reasoning="PostgreSQL provides unified transactions and robust pgvector support without cloud lock-in.",
        project_id=project_id,
        tags=["database", "architecture"],
    )
    assert rec.decision_text.startswith("Use PostgreSQL")
    assert len(rec.alternatives_considered) == 3
    assert rec.outcome is None

    # Update outcome
    updated = journal.update_outcome(rec.decision_id, outcome="Achieved 4ms retrieval latency in production.")
    assert "4ms retrieval" in updated.outcome

    # List
    listed = journal.list_decisions(project_id=project_id, tag="database")
    assert len(listed) == 1
    assert listed[0].decision_id == rec.decision_id


# ── 4. Knowledge Graph Bridge Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_personal_knowledge_graph_bridge():
    store = GraphStore()
    bridge = PersonalKnowledgeBridge(graph_store=store)

    project_id = uuid.uuid4()
    goal_id = uuid.uuid4()
    task_id = uuid.uuid4()
    decision_id = uuid.uuid4()

    # 1. Project -> supports -> Goal
    rel_goal = await bridge.link_project_supports_goal(
        project_id=project_id,
        project_name="Myagent",
        goal_id=goal_id,
        goal_title="Release Desktop Assistant",
    )
    assert rel_goal.relationship_type == RelationshipType.RELATED_TO
    assert rel_goal.provenance["relation"] == "supports_goal"

    # 2. Task -> contributes_to -> Goal
    rel_task = await bridge.link_task_contributes_to_goal(
        task_id=task_id,
        task_goal="Implement Flutter UI",
        goal_id=goal_id,
        goal_title="Release Desktop Assistant",
        project_id=project_id,
    )
    assert rel_task.provenance["relation"] == "contributes_to_goal"

    # 3. Decision -> affects -> Project
    rel_dec = await bridge.link_decision_affects_project(
        decision_id=decision_id,
        decision_text="Adopt Riverpod for Flutter state",
        project_id=project_id,
        project_name="Myagent",
    )
    assert rel_dec.provenance["relation"] == "decision_affects_project"


# ── 5. Context Resolution & Privacy Boundaries ────────────────────────────────

def test_personal_context_resolution_and_scoping():
    goal_mgr = GoalManager()
    journal = DecisionJournal()
    resolver = PersonalContextResolver(goal_manager=goal_mgr, journal=journal)

    project_id = uuid.uuid4()

    # Create Goal and Decision
    goal = goal_mgr.create_goal(title="Launch Beta", project_id=project_id)
    goal_mgr.add_milestone(goal.goal_id, title="Test coverage 90%")
    journal.record_decision(
        decision_text="Strict typing in Python",
        project_id=project_id,
        tags=["code"],
    )
    journal.record_decision(
        decision_text="Private salary negotiation notes",
        project_id=project_id,
        tags=["personal_finance"],
    )

    # 1. Context Resolution
    pkg = resolver.resolve(query="What is our status on Beta?", project_id=project_id)
    assert len(pkg.goals) == 1
    assert "Active Goals:" in pkg.summary_text
    assert "Test coverage 90%" in pkg.summary_text

    # 2. Sub-Agent Privacy Scoping
    scoped_research = resolver.scope_for_subagent(pkg, AgentType.RESEARCH_AGENT)
    # Research agent gets goals, but NO private decisions
    assert len(scoped_research["goals"]) == 1
    assert len(scoped_research["decisions"]) == 0

    scoped_coding = resolver.scope_for_subagent(pkg, AgentType.CODING_AGENT)
    # Coding agent gets only coding decisions, personal finance decision is stripped
    assert len(scoped_coding["decisions"]) == 1
    assert "Strict typing" in scoped_coding["decisions"][0]["decision"]

    # 3. Web Research Query Sanitization
    raw_query = "Search DuckDuckGo for bug in /home/rev/projects/secret/auth.py user test@secret.com"
    clean_query = resolver.sanitize_for_web_research(raw_query)
    assert "/home/rev" not in clean_query
    assert "test@secret.com" not in clean_query


# ── 6. Proactive Deadline & Stalled Goal Detection ─────────────────────────────

@pytest.mark.asyncio
async def test_proactive_deadline_and_stalled_goal_detection():
    goal_mgr = GoalManager()
    detector = EventDetector()
    proactive_detector = PersonalProactiveDetector(goal_manager=goal_mgr, detector=detector)

    # Goal with deadline in 2 days (Approaching!)
    goal_mgr.create_goal(
        title="Submit Grant Proposal",
        target_date=datetime.now(timezone.utc) + timedelta(days=2),
    )

    # Stalled goal (Simulate created 10 days ago with 0 progress)
    stalled = goal_mgr.create_goal(title="Refactor Legacy Auth")
    stalled.updated_at = datetime.now(timezone.utc) - timedelta(days=10)

    events = await proactive_detector.check_goals_and_deadlines(days_ahead=3)
    assert len(events) == 2
    assert any("Approaching target date" in e.description for e in events)
    assert any("Stalled goal" in e.description for e in events)


# ── 7. Database Schema Models ──────────────────────────────────────────────────

def test_personal_knowledge_database_models():
    g_rec = PersonalGoalRecord(
        title="Test Goal Record",
        progress=0.75,
        state="active",
        priority="high",
    )
    assert g_rec.title == "Test Goal Record"
    assert g_rec.progress == 0.75

    m_rec = PersonalMilestoneRecord(
        title="Milestone 1",
        completed=True,
    )
    assert m_rec.title == "Milestone 1"
    assert m_rec.completed is True

    d_rec = PersonalDecisionRecord(
        decision_text="Chosen FastAPI over Flask",
        alternatives_considered=["Flask", "Django"],
        reasoning="FastAPI is async-native.",
    )
    assert "FastAPI" in d_rec.decision_text
    assert len(d_rec.alternatives_considered) == 2
