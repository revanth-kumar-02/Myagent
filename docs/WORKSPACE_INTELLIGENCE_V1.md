# Kora Workspace & Project Intelligence Architecture (V18)

## 1. Overview & Purpose
The **Workspace & Project Intelligence Engine (V18)** provides Kora with a unified, cross-layer understanding of projects and multi-project workspaces. It bridges all existing Kora intelligence layers—Files, Documents, Code, Knowledge Graph, Memories, Tasks, Goals, Decisions, Agents, and Activity—into coherent project representations while maintaining strict project isolation and evidence-based facts.

```
+-----------------------------------------------------------------------------------+
|                                 WORKSPACE                                         |
|  +-----------------------------------------------------------------------------+  |
|  |                             ACTIVE PROJECT                                  |  |
|  |  +---------------+  +---------------+  +---------------+  +---------------+ |  |
|  |  |  Files & Code |  |   Knowledge   |  |   Memories    |  | Tasks & Goals | |  |
|  |  +---------------+  +---------------+  +---------------+  +---------------+ |  |
|  |  +---------------+  +---------------+  +---------------+  +---------------+ |  |
|  |  | Decisions/Jrnl|  | Multi-Agents  |  | Activity Strm |  | Fact-Health   | |  |
|  |  +---------------+  +---------------+  +---------------+  +---------------+ |  |
|  +-----------------------------------------------------------------------------+  |
|                          Unified Project Context Layer                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Components

### 2.1 Workspace & Project Management (`apps/agent/workspace/manager.py`)
- **Workspace Data Model**: Manages multiple `ProjectProfile` instances with a single designated `active_project_id`.
- **Project Switching**: Cleanly transitions agent focus between projects and triggers contextual reload.
- **Archive & Safety Guard**: Allows soft-archiving of inactive projects and protects active projects against accidental deletion.
- **Activity Logging**: Emits append-only `ProjectActivityEvent` records to database/memory.

### 2.2 Project Discovery Engine (`apps/agent/workspace/discovery.py`)
- **Factual Inspection**: Scans project directories using file tools and non-blocking traversal.
- **Language & Framework Detection**: Detects languages (Python, Dart/Flutter, TypeScript, Go, Rust, C++, Java, Swift) and frameworks (FastAPI, Django, Flutter, React, Next.js, Vue) via manifest inspection (`pyproject.toml`, `pubspec.yaml`, `package.json`, `Cargo.toml`, etc.).
- **Structure Discovery**: Pinpoints entry points (`main.py`, `app.py`, `main.dart`, `index.ts`, `main.go`, `main.rs`), config files, test directories, documentation (`README.md`, `ARCHITECTURE.md`), and database files.
- **Zero Hallucination Rule**: Strictly derives technologies and architecture from discovered files and contents without guessing.

### 2.3 Evidence-Based Project Health Engine (`apps/agent/workspace/health.py`)
- **Fact-Based Health**: Computes deterministic health metrics from real system data:
  - `active_tasks_count`, `failed_tasks_count`, `blocked_tasks_count`
  - `active_goals_count`, `completed_goals_count`
  - `open_decisions_count`
  - `memory_count`
  - `recent_activity_count`
- **Zero Invented Metrics**: Categorizes health status (`HEALTHY`, `NEEDS_ATTENTION`, `BLOCKED`, `STALE`, `UNKNOWN`) strictly through explicit mathematical and rule-based thresholds.

### 2.4 Unified Project Context Builder (`apps/agent/workspace/context.py`)
- **Cross-Layer Aggregation**: Merges:
  - `ProjectProfile` & `ProjectDiscoveryResult`
  - Long-term/Episodic memories tagged for `project_id`
  - Knowledge graph entities and relationships linked to the project
  - Tasks and Workflows associated with the project
  - Personal Goals and Milestones
  - Decision Journal entries
  - Recent activity events
- **Multi-Project Boundary Isolation**: Automatically applies `project_id` filters to prevent cross-project contamination or memory leakage.

### 2.5 Proactive Workspace Hooks (`apps/agent/workspace/proactive_hooks.py`)
- **Workspace Event Detection**: Integrates with the V15 Proactive Intelligence Engine to trigger non-intrusive notifications on:
  - Newly discovered or unindexed projects
  - Critical task failures or blocked goals within the active project
  - Stale projects with pending goals

---

## 3. Database Schema (`infra/migrations/007_workspace_schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS workspace_activity_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    summary TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Flutter Desktop UI Presentation (`apps/desktop/lib/features/projects/`)
1. `workspace_view.dart`: Multi-project workspace overview, active project switcher, and project creation modal.
2. `project_overview_widget.dart`: Project profile header, discovered technologies, directories, and entry points.
3. `project_health_widget.dart`: Health badge, blocked/failed task counts, goal completion bar, and fact metrics.
4. `project_activity_widget.dart`: Real-time chronological activity stream with actor badges and formatted timestamps.
