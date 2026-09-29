# Kora — Capability → Frontend Audit

**Audit Date:** 2026-09-29
**Auditor:** Antigravity
**Scope:** Full backend-to-frontend capability traceability
**Method:** Static code analysis across `apps/agent/` (Python/FastAPI) and `apps/desktop/lib/` (Dart/Flutter/Riverpod)

---

## Legend

| Code | Meaning |
|------|---------|
| **A** | Fully exposed and working — backend real, API real, frontend connected |
| **B** | Exposed but partially connected — some path broken or incomplete |
| **C** | Backend exists but no usable frontend surface |
| **D** | Frontend exists but backend connection is fake/broken |
| **E** | Placeholder / mock / hardcoded data |
| **F** | Duplicate / obsolete / dead code |
| **G** | Missing implementation (both sides) |

---

## Full Capability Audit Table

| # | Capability | Backend Status | Frontend Surface | Connected? | Real/Mock | API/WS Contract | Missing UI | Grade |
|---|------------|---------------|-----------------|-----------|-----------|-----------------|-----------|-------|
| 1 | Chat/Agent | Full — `core/session.py`, `core/planner.py` | `features/chat/chat_screen.dart` | Yes — WS | Real | `WS CHAT_REQUEST → CHAT_DONE` | Streaming chunks; plan steps not persisted | **A** |
| 2 | Model Router | Full — `core/model_router.py`, `models/registry.yaml` | Header pill only | Partial | Real | `GET /api/models` | No per-conversation model selector | **B** |
| 3 | Cloud AI (HuggingFace) | `models/providers/` | None direct | Background via chat | Real (when key set) | N/A | Provider health screen | **C** |
| 4 | Ollama Fallback | `ollama-chat` in registry + `ollama_direct_service.dart` | Auto-fallback in chat | Auto | Real | Direct Ollama HTTP | No explicit "using Ollama" indicator | **B** |
| 5 | Provider Failover | `models/failover.py`, `GET /api/health/providers` | None | No | Real | `GET /api/health/providers` | Provider health panel | **C** |
| 6 | Tool System | `tools/` — files, git, web, system, computer, browser, dev | Chat-only (via agent) | Indirectly | Real | WS session | Tool call history in chat | **B** |
| 7 | Tool Registry / List | `tools/registry.py`, `GET /api/tools` | No dedicated viewer | Partial | Real | `GET /api/tools` | Tools browser / slash palette | **B** |
| 8 | Web Search / Research | `research/router.py` → DuckDuckGo | `features/research/research_screen.dart` | Yes | Real | `POST /api/research` | No result history or caching | **A** |
| 9 | Project RAG | `rag/indexer.py`, `rag/retriever.py` | Projects screen → Index button | Yes | Real | `WS INDEX_REQUEST → INDEX_DONE` | RAG query UI; chunk viewer | **B** |
| 10 | Memory | `memory/manager.py` → PostgreSQL | `features/memory/memory_screen.dart` | Yes | Real | `GET/POST/PATCH/DELETE /api/memory` | Bulk ops missing | **A** |
| 11 | Knowledge Graph | `graph/service.py` → PostgreSQL | Memory screen graph tab | Yes | Real (stub fallback on DB error) | `GET /api/memory/graph` | Graph visualisation is text-only list | **B** |
| 12 | Projects / File Explorer | `GET /api/projects/fs/*` — real FS scan | `features/projects/projects_screen.dart` | Yes | Real | REST | No file diff/edit; launch partial | **B** |
| 13 | Document Reader | `GET /api/projects/fs/file` — text/image/pdf preview | Project screen file viewer | Yes | Real | REST | PDF and binary preview missing | **B** |
| 14 | VISION (Image Analysis) | `vision/analyzer.py` exists but returns HARDCODED fake elements — model is NEVER called | `features/vision/presentation/` — 7 Dart files NOT in navigation | NO ENDPOINT EXISTS | Mock/Hardcoded | NO /api/vision/* endpoint | Full Vision workspace | **E (highest priority)** |
| 15 | OCR / Text Extraction | No dedicated OCR; analyzer extracts element labels only | None | None | Mock | None | OCR result panel in Vision screen | **G** |
| 16 | Screen Capture | `vision/capture.py` — real platform adapter | `screen_intelligence_view.dart` — `Future.delayed` SIMULATION | Fake | Hardcoded mock | No endpoint | Capture trigger in Vision | **E** |
| 17 | Browser / Computer Control | `tools/computer.py`, `tools/browser.py` | None direct | Chat-only tool | Real (platform dependent) | Via WS agent | Computer control panel | **C** |
| 18 | Tasks / Automations | Full — `tasks/manager.py`, `tasks/automation.py` | `features/tasks/tasks_screen.dart` | Yes | Real | Full CRUD REST | Execution step trace missing | **A** |
| 19 | Automation Templates | Hardcoded list in `http.py` | Tasks screen | Yes | Hardcoded static | `GET /api/automations/templates` | Template editing | **B** |
| 20 | Scheduling | `tasks/automation.py` — APScheduler | Tasks screen trigger config | Yes | Real | Via automation create | No cron builder UI | **B** |
| 21 | Activity / Telemetry | `GET /api/activity` — in-memory ring buffer (200 items, RESETS ON RESTART) | `features/activity/activity_screen.dart` | Yes | Real (ephemeral) | `GET /api/activity` | Not persisted across restarts | **B** |
| 22 | System Monitor | `observability/system_monitor.py` — psutil CPU/RAM/disk | Home screen + header indicator | Yes | Real | `GET /api/system/metrics` | Historical charts missing | **B** |
| 23 | Notifications | None | None | None | None | None | Notification center | **G** |
| 24 | Permissions | `permissions/gate.py` — WS PERMISSION_RESPONSE | Chat permission dialogs | Yes | Real | `WS PERMISSION_RESPONSE` | Permission history/audit | **A** |
| 25 | Code Execution | `tools/dev.py` — subprocess/shell | Chat-only | Indirectly | Real | Via WS agent | Code block run button in chat | **C** |
| 26 | Git | `tools/dev.py` git_ops | Chat-only | Indirectly | Real | Via WS agent | Git status panel in Projects | **C** |
| 27 | Database Tools | None | None | None | None | None | — | **G** |
| 28 | File Operations | `tools/files.py` — read/write/list/delete | Chat + project tree | Partially | Real | Via WS agent + REST | Batch file ops UI | **B** |
| 29 | Image Generation / Editing | None | None | None | None | None | — | **G** |
| 30 | Audio / STT / TTS | `voice/` dir + `gemma-audio` in registry | `features/voice/` present | Not connected | Unknown | None | Voice input button in chat | **C** |
| 31 | Agent Delegation / Sub-agents | `orchestration/` dir | None | No | Unknown | None | Delegation transparency in chat | **C** |
| 32 | Observability / Replay | `observability/` dir + activity logs | `features/observability/` | Partial | Real | `GET /api/activity` | Execution replay viewer | **B** |
| 33 | Settings / Configuration | Backend env config | `features/settings/settings_screen.dart` | Yes | Real (local Riverpod + shared_prefs) | Local only | Backend settings API missing | **B** |
| 34 | Online / Offline / Degraded | `models/failover.py` health checks | Connection pill + status indicator | Yes | Real | `GET /api/health/providers` | Degraded mode banner | **B** |
| 35 | Learning / Personal Adaptation | `learning/` dir | None | None | Unknown | None | — | **C** |
| 36 | Proactive Agent | `proactive/` dir | None | None | Unknown | None | — | **C** |
| 37 | Personal Context | `personal/` dir | None | None | Unknown | None | — | **C** |
| 38 | Google Tasks | `tools/google/tasks_tools.py` | None direct | Chat-only | Real (needs OAuth) | Via WS agent | Google tasks panel | **C** |
| 39 | Workspace Management | `workspace/` dir | Projects screen | Partial | Partial | REST | Workspace switcher | **B** |

---

## Critical Findings

### VISION — Grade E / Highest Priority

**Backend (vision/analyzer.py):**
- Routes to `gemma-vision` model via `ModelRouter.select("vision")` — architecture correct
- BUT: the actual model call is NOT implemented. When no `mock_elements` are passed, analyzer
  returns two hardcoded raw_elements (Settings button + Search input) regardless of image content
- `vision/capture.py` — real platform adapter call exists; may actually capture on Linux/macOS
- `vision/context.py` — fully functional; builds `ScreenContext` from any `VisualAnalysisResult`
- **NO HTTP endpoints exist for any vision operation** — entire module has zero API surface

**Frontend (features/vision/presentation/*.dart):**
- 7 Dart files exist but are completely orphaned (not in sidebar, not in app_shell)
- `screen_intelligence_view.dart` uses `Future.delayed(600ms)` to SIMULATE capture
- Detected elements are hardcoded Dart maps — not from any API call
- These files have NEVER been accessible to a user

### Activity Log Persistence — Grade B (Critical Bug)
`_activity_store` in `api/http.py` is a plain Python list. Resets on every backend restart.

### Automation Interpretation — Grade E (Hidden Mock)
`POST /api/automations/interpret` uses Python `in` string checks, NOT an LLM call.
Despite being named "interpret", it is hardcoded keyword matching.

---

## Dead / Orphaned Code

| File / Module | Issue |
|--------------|-------|
| `features/vision/presentation/screen_intelligence_view.dart` | Not in navigation; mock delays |
| `features/vision/presentation/visual_workflow_view.dart` | Not in navigation; no backend |
| `features/vision/presentation/workflow_runner_widget.dart` | Not in navigation; no backend |
| `features/vision/presentation/workflow_step_builder_widget.dart` | Not in navigation |
| `vision/workflows/` (entire backend) | Full workflow engine; zero frontend surface |

---

## Part 3 — UI Gap Map

| Capability | Recommended Access Point |
|-----------|-------------------------|
| Vision (analyze, OCR, VQA) | **Main navigation workspace** |
| Screen Capture | **Vision workspace** |
| Send Visual Context to Chat | **Vision workspace → Chat handoff button** |
| Provider Health | **Settings → Providers** |
| Ollama status | **Connection pill (extend existing)** |
| Tool browser / slash commands | **Chat input palette** |
| Code execution results | **Chat (structured tool call block)** |
| Git status | **Projects workspace → contextual panel** |
| Knowledge Graph visualisation | **Memory screen → Graph tab (add render)** |
| Audio/STT | **Chat input mic button** |
| Notifications | **Header bell icon (new)** |
| Proactive suggestions | **Home dashboard** |
| Learning/personalization | **Settings → Personalization** |
| Agent delegation transparency | **Chat (sub-agent call bubbles)** |
| Execution step trace | **Tasks workspace → execution detail** |
| Database tools | **Chat-integrated** |
| Image generation | **Chat-integrated + Vision workspace** |
| Activity persistence | **Backend fix** (PostgreSQL) |

---

## Priority Implementation Order

1. **Vision workspace + API endpoints** — zero surface, highest user value
2. **Provider health in Settings** — endpoint exists, needs 1 panel
3. **Tool call transparency in Chat** — structured tool call bubbles
4. **Knowledge Graph visualisation** — data exists, needs render widget
5. **Activity log persistence** — backend: write to PostgreSQL
6. **Voice/STT** — model in registry, needs platform wire-up
7. **Notification center** — new feature
