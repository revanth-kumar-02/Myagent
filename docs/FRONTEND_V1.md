# Kora Desktop Frontend Architecture Specification (V1)

## Overview

The Kora Desktop Frontend is built with Flutter and Dart, targeting cross-platform desktop operating systems (Linux, Windows, macOS). It provides a clean, responsive, desktop-first user interface connected to the local FastAPI and WebSocket backend.

---

## Directory Structure

```
apps/desktop/lib/
├── core/
│   ├── config/
│   │   └── app_config.dart
│   ├── networking/
│   │   ├── api_client.dart
│   │   └── ws_client.dart
│   ├── theme/
│   │   └── app_theme.dart
│   └── utils/
│       └── date_formatter.dart
├── models/
│   ├── activity_log.dart
│   ├── chat_message.dart
│   ├── citation.dart
│   ├── memory_item.dart
│   ├── model_info.dart
│   ├── plan_step.dart
│   ├── project.dart
│   ├── research_result.dart
│   └── task_item.dart
├── services/
│   ├── kora_api_service.dart
│   └── kora_socket_service.dart
├── state/
│   ├── activity_state.dart
│   ├── chat_state.dart
│   ├── connection_state.dart
│   ├── memory_state.dart
│   ├── projects_state.dart
│   ├── research_state.dart
│   ├── settings_state.dart
│   └── tasks_state.dart
├── widgets/
│   ├── app_shell.dart
│   ├── citation_card.dart
│   ├── plan_progress_card.dart
│   ├── sidebar.dart
│   ├── status_pill.dart
│   └── tool_badge.dart
├── features/
│   ├── activity/
│   │   └── activity_screen.dart
│   ├── chat/
│   │   └── chat_screen.dart
│   ├── home/
│   │   └── home_screen.dart
│   ├── memory/
│   │   └── memory_screen.dart
│   ├── projects/
│   │   └── projects_screen.dart
│   ├── research/
│   │   └── research_screen.dart
│   ├── settings/
│   │   └── settings_screen.dart
│   └── tasks/
│       └── tasks_screen.dart
├── app.dart
└── main.dart
```

---

## Screen Catalog

1. **App Shell & Navigation (`Sidebar`)**:
   - Collapsible desktop sidebar with brand header, active route indicators, and quick status pill.
   - Status pill reflects real-time server connectivity (`Connected`, `Connecting...`, `Offline`).

2. **Home Dashboard (`HomeScreen`)**:
   - System overview cards: server health, available models count, active projects, running tasks.
   - Quick action launchers: Web Research, Long-term Memory Bank, Model Capability Registry.
   - Live activity event summary feed.

3. **Primary Chat Screen (`ChatScreen`)**:
   - Full conversational interface with auto-scrolling message list.
   - Real-time token streaming (`CHAT_CHUNK`).
   - Dynamic multi-step Plan Progress Timeline (`PlanProgressCard`).
   - Active tool execution badges (`ToolBadge`).
   - Source citations viewer (`CitationCard`) for local RAG chunks and external DuckDuckGo web sources.
   - Stop generation / cancel request action button.
   - Project workspace scope selector dropdown.

4. **Workspace Projects (`ProjectsScreen`)**:
   - View, create, and delete workspace project records.
   - Displays indexed file count, chunk count, and root workspace directory path.

5. **Agent Tasks (`TasksScreen`)**:
   - Real-time task board showing running and completed agent background tasks, categories, and execution durations.

6. **Web Research (`ResearchScreen`)**:
   - Ad-hoc DuckDuckGo search interface with query input, result snippets, source links, and relevance scores.

7. **Agent Memory (`MemoryScreen`)**:
   - Explore stored agent memories with category filtering (Preferences, Facts, Decisions, Task Context).
   - Add new memory entries and delete outdated memories.

8. **Settings (`SettingsScreen`)**:
   - Configure REST and WebSocket endpoint URLs with live connectivity test.
   - Dark / Light theme toggle.
   - Model Registry capabilities viewer (exposing roles and context limits without secrets).

---

## State Management Architecture

State is managed via **Flutter Riverpod** using `StateNotifier` and immutable state classes:
- `ConnectionNotifier`: Monitors backend health and status.
- `ChatNotifier`: Manages conversational turn state, WebSocket message listener, streaming chunks, tool execution badges, plan step updates, and cancellation.
- `ProjectsNotifier`: Handles workspace projects CRUD.
- `TasksNotifier`: Synchronizes task status.
- `ResearchNotifier`: Executes DuckDuckGo web searches.
- `ActivityNotifier`: Fetches observability events.
- `MemoryNotifier`: Manages long-term memory records.
- `SettingsNotifier`: Manages theme mode, URLs, and model metadata.
