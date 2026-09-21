"""
tests.agent.test_workspace_v18 — Test Suite for Kora Workspace & Project Intelligence (V18)

Verifies:
  1. Workspace & Project lifecycle: creation, retrieval, active project switching, archiving, deletion guard
  2. Automated Codebase Discovery: languages, frameworks, entry points, config files, test structure
  3. Factual Project Health Engine: zero invented values, accurate status derivation
  4. Unified Project Context & Multi-Project Isolation: ensuring zero cross-project leakage
  5. Automatic project detection from user queries
  6. Project activity logging and stream querying
  7. Proactive workspace health detection
  8. Database schema models
"""

import uuid
from pathlib import Path

import pytest

from personal.journal import DecisionJournal
from personal.manager import GoalManager
from proactive.detector import EventDetector
from workspace.context import ProjectContextBuilder
from workspace.discovery import ProjectDiscoveryEngine
from workspace.health import ProjectHealthEngine
from workspace.manager import ProjectNotFoundError, WorkspaceActionError, WorkspaceManager
from workspace.proactive_hooks import WorkspaceProactiveDetector
from workspace.types import (
    ActivityType,
    IndexingStatus,
    ProjectHealthStatus,
    ProjectStatus,
)
from db.schema import WorkspaceActivityRecord


# ── 1. Workspace Lifecycle Tests ──────────────────────────────────────────────

def test_workspace_and_project_lifecycle():
    mgr = WorkspaceManager()

    # 1. Create Project
    p1 = mgr.create_project(
        name="Kora Assistant",
        root_path="/home/rev/projects/kora",
        description="Local AI Agent",
        auto_discover=False,
    )
    assert p1.name == "Kora Assistant"
    assert p1.status == ProjectStatus.ACTIVE
    assert mgr.get_active_project().project_id == p1.project_id

    # 2. Create Second Project
    p2 = mgr.create_project(
        name="Website Landing",
        root_path="/home/rev/projects/landing",
        auto_discover=False,
    )
    assert len(mgr.list_projects()) == 2

    # 3. Switch Active Project
    switched = mgr.set_active_project(p2.project_id)
    assert switched.project_id == p2.project_id
    assert mgr.get_active_project().project_id == p2.project_id

    # 4. Archive Project
    archived = mgr.archive_project(p2.project_id)
    assert archived.status == ProjectStatus.ARCHIVED
    assert mgr.get_active_project() is None  # Active project cleared if archived

    # 5. Deletion Guard
    with pytest.raises(WorkspaceActionError):
        mgr.delete_project(p1.project_id, confirm=False)

    deleted = mgr.delete_project(p1.project_id, confirm=True)
    assert deleted is True
    assert mgr.get_project(p1.project_id) is None


# ── 2. Automated Codebase Discovery Tests ──────────────────────────────────────

def test_project_discovery_engine_real_repo():
    engine = ProjectDiscoveryEngine()
    current_repo_root = Path(__file__).resolve().parents[2]

    res = engine.discover(current_repo_root)

    # Verify Languages
    assert "Python" in res.languages
    assert "Dart" in res.languages

    # Verify Frameworks
    assert "FastAPI" in res.frameworks or "SQLAlchemy" in res.frameworks

    # Verify Important Directories
    assert "apps" in res.important_directories
    assert "tests" in res.important_directories
    assert "docs" in res.important_directories

    # Verify Config Files
    assert any("pyproject.toml" in c for c in res.config_files)

    # Verify Test Structure
    assert any("tests" in t for t in res.test_structure)


def test_project_discovery_engine_simulated():
    engine = ProjectDiscoveryEngine()
    simulated_files = [
        "src/main.rs",
        "Cargo.toml",
        "README.md",
        "tests/test_basic.rs",
        "infra/docker-compose.yml",
    ]

    res = engine.discover(root_path="/tmp/fake_rust_project", file_list=simulated_files)
    assert "Rust" in res.languages
    assert "Cargo.toml" in res.config_files
    assert "src/main.rs" in res.entry_points
    assert "README.md" in res.doc_files
    assert "tests/test_basic.rs" in res.test_structure


# ── 3. Factual Health Engine Tests ────────────────────────────────────────────

def test_project_health_engine_factual_metrics():
    engine = ProjectHealthEngine()
    mgr = WorkspaceManager()
    project = mgr.create_project(name="Health Test", root_path="/test", auto_discover=False)
    project.doc_files = ["README.md"]

    # 1. Unindexed project with files -> NEEDS_ATTENTION
    h1 = engine.compute_health(
        project=project,
        total_files=20,
        total_chunks=0,
    )
    assert h1.indexing_status == IndexingStatus.NOT_INDEXED
    assert h1.health_status == ProjectHealthStatus.NEEDS_ATTENTION
    assert any("search index is not built" in issue for issue in h1.issues)

    # 2. Indexed healthy project -> HEALTHY
    h2 = engine.compute_health(
        project=project,
        total_files=20,
        total_chunks=65,
    )
    assert h2.indexing_status == IndexingStatus.INDEXED
    assert h2.health_status == ProjectHealthStatus.HEALTHY
    assert len(h2.issues) == 0


# ── 4. Unified Context & Multi-Project Isolation ──────────────────────────────

@pytest.mark.asyncio
async def test_unified_project_context_and_isolation():
    workspace_mgr = WorkspaceManager()
    goal_mgr = GoalManager()
    journal = DecisionJournal()
    context_builder = ProjectContextBuilder(
        workspace_manager=workspace_mgr,
        goal_manager=goal_mgr,
        journal=journal,
    )

    # Create Project Alpha and Project Beta
    p_alpha = workspace_mgr.create_project(name="Project Alpha", root_path="/alpha", auto_discover=False)
    p_beta = workspace_mgr.create_project(name="Project Beta", root_path="/beta", auto_discover=False)

    # Attach Goal and Decision to Alpha
    goal_mgr.create_goal(title="Alpha Unique Goal", project_id=p_alpha.project_id)
    journal.record_decision(
        decision_text="Alpha Unique Architectural Decision",
        project_id=p_alpha.project_id,
    )

    # Attach Goal to Beta
    goal_mgr.create_goal(title="Beta Unique Goal", project_id=p_beta.project_id)

    # 1. Build Context for Alpha
    ctx_alpha = await context_builder.build_project_context(p_alpha.project_id)
    assert "Alpha Unique Goal" in ctx_alpha.summary_text
    assert "Alpha Unique Architectural Decision" in ctx_alpha.summary_text
    assert "Beta Unique Goal" not in ctx_alpha.summary_text  # ISOLATION GUARANTEE!

    # 2. Build Context for Beta
    ctx_beta = await context_builder.build_project_context(p_beta.project_id)
    assert "Beta Unique Goal" in ctx_beta.summary_text
    assert "Alpha Unique Goal" not in ctx_beta.summary_text  # ISOLATION GUARANTEE!
    assert "Alpha Unique Architectural Decision" not in ctx_beta.summary_text  # ISOLATION GUARANTEE!


# ── 5. Project Detection From Query ───────────────────────────────────────────

def test_detect_project_from_query():
    workspace_mgr = WorkspaceManager()
    context_builder = ProjectContextBuilder(workspace_manager=workspace_mgr)

    p1 = workspace_mgr.create_project(name="Desktop Client", root_path="/apps/desktop", auto_discover=False)
    p2 = workspace_mgr.create_project(name="Agent Core", root_path="/apps/agent", auto_discover=False)

    detected1 = context_builder.detect_project_from_query("What is the state of Desktop Client?")
    assert detected1 == p1.project_id

    detected2 = context_builder.detect_project_from_query("Refactor files in /apps/agent/main.py")
    assert detected2 == p2.project_id

    detected_none = context_builder.detect_project_from_query("What is the weather today?")
    assert detected_none is None


# ── 6. Activity Tracking Stream ───────────────────────────────────────────────

def test_project_activity_stream():
    mgr = WorkspaceManager()
    p = mgr.create_project(name="Stream Test", root_path="/stream", auto_discover=False)

    mgr.record_activity(
        project_id=p.project_id,
        activity_type=ActivityType.INDEXING,
        title="RAG Indexing Completed",
        description="Parsed 45 chunks.",
    )
    mgr.record_activity(
        project_id=p.project_id,
        activity_type=ActivityType.GOAL,
        title="Milestone Finished",
        description="Goal reached 50%.",
    )

    activities = mgr.list_activity(project_id=p.project_id)
    assert len(activities) >= 3  # Initial creation + 2 manual activities
    assert activities[0].title == "Milestone Finished"


# ── 7. Proactive Workspace Health Detection ───────────────────────────────────

@pytest.mark.asyncio
async def test_proactive_workspace_detector():
    workspace_mgr = WorkspaceManager()
    detector = EventDetector()
    proactive = WorkspaceProactiveDetector(workspace_manager=workspace_mgr, detector=detector)

    # Project with entry points but not indexed
    p = workspace_mgr.create_project(name="Unindexed Service", root_path="/service", auto_discover=False)
    p.entry_points = ["main.py"]

    events = await proactive.scan_workspace_health()
    assert len(events) == 1
    assert "Unindexed Project: Unindexed Service" in events[0].title


# ── 8. Database Schema Models ──────────────────────────────────────────────────

def test_workspace_activity_db_model():
    rec = WorkspaceActivityRecord(
        project_id=uuid.uuid4(),
        activity_type="indexing",
        title="Test Activity",
        description="Completed chunking",
        metadata_={"chunks": 10},
    )
    assert rec.activity_type == "indexing"
    assert rec.metadata_["chunks"] == 10
