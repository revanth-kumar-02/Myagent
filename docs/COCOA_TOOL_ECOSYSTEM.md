# Cocoa Autonomous Personal Agent: 7-Pillar Ecosystem Specification

> **OFFICIAL ARCHITECTURAL SPECIFICATION & CANONICAL TAXONOMY**  
> This document defines the unified **7 Main Pillars** of Cocoa as an autonomous personal AI agent (J.A.R.V.I.S. architecture), consolidating all cognitive capabilities, perceptual systems, OS tools, and personal assistant features into a cohesive execution model.  
> **Status**: SPECIFICATION LOCKED. No new tools implemented in this phase. Existing tools fully preserved.

---

## 1. The 7 Canonical Pillars Matrix

All of Cocoa's cognitive abilities, autonomous agency, multimodal perception, and 50 locked tools are categorized into **7 core pillars**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       COCOA 7-PILLAR TAXONOMY                                           │
├────────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ 1. 🧠 CORE INTELLIGENCE & AUTONOMOUS AGENCY        │ Cognitive reasoning, DAG planning, multi-agents.   │
│ 2. 🖱️ COMPUTER CONTROL & OS INTERACTION            │ Native mouse, keyboard, windows, and filesystem.   │
│ 3. 👁️ VISION & MULTIMODAL PERCEPTION               │ Screen understanding, OCR, and visual grounding.   │
│ 4. 🗣️ VOICE & CONVERSATIONAL INTERACTION           │ Speech-to-text, TTS, wake word, voice dialogue.    │
│ 5. 🌐 WEB INTELLIGENCE & RESEARCH                  │ Live web search, browser automation, web monitors. │
│ 6. 📚 KNOWLEDGE, DOCUMENTS & MEMORY                │ Project RAG, long-term memory, document parsing.   │
│ 7. 📅 PERSONAL ASSISTANT & LIFE OPERATIONS         │ Calendar, tasks, email, messaging, finance, habits.│
└────────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Classification: Features & Tools Across the 7 Pillars

---

### Pillar 1: 🧠 Core Intelligence & Autonomous Agency
*The central brain of Cocoa responsible for reasoning, strategic multi-step execution, self-correction, and coordinating child agents.*

#### Core Cognitive Capabilities
- **Natural Language Understanding (NLU)**: Deep intent extraction, semantic slot filling, and tone awareness.
- **Context Awareness**: Dynamic situational modeling of current workspace, active tasks, time of day, and environment.
- **Persistent Memory & Preference Learning**: Adaptive modeling of user habits, communication preferences, and past decisions.
- **Long-Term Goals & Conversational Continuity**: Tracking ongoing multi-week objectives across multiple interaction sessions.
- **Proactive Suggestions & Decision Making**: Anticipating the next logical move and lowering activation energy.
- **Self-Reflection, Self-Correction & Replanning**: Detecting step failures, classifying root causes, and re-routing DAG plans without human intervention.
- **Long-Running & Scheduled Workflows**: Event-based triggers, cron daemons, and persistent task state across restarts.
- **Multi-Agent Orchestration**:
  - Sub-agent creation & task delegation
  - Parallel agent execution & inter-agent communication
  - Agent handoff, supervision, and shared context synchronization

#### Mapped Tools & Execution Capabilities
- **`Code Executor` (Tool 47)**: Sandboxed terminal and script execution (`terminal` tool).
- **`Database Tool` (Tool 48)**: Query introspection and relational database management.
- **`Git Tool` (Tool 49)**: Version control inspection, diffing, and branch management (`git_*` tools).
- **`Agent Delegation` (Tool 50)**: Spawning and aggregating child sub-agents.
- **`Automation Scheduler` (Tool 30)**: Background scheduling and delayed execution daemon (`scheduler` tool).

---

### Pillar 2: 🖱️ Computer Control & OS Interaction
*Direct desktop agency allowing Cocoa to operate the user's computer alongside them.*

#### Core Interaction Capabilities
- **Mouse & Keyboard Control**: Synthetic click, double click, drag-and-drop, typing, key combinations, and text entry.
- **Application Lifecycle**: Launching installed desktop apps, application switching, and graceful termination.
- **Window Management**: Window state detection, tiling, minimizing, maximizing, focusing, and multi-monitor management.
- **Filesystem Management**: Navigating directories, searching by pattern/content, atomic file writes, moves, and trash.
- **Clipboard Management**: Bidirectional read/write access to system clipboard (text, rich text, image data).
- **System Settings & Notifications**: Native OS notification banners, audio chime alerts, volume, and display power control.

#### Mapped Tools
- **`App Launcher` (Tool 01)**: Desktop app lifecycle execution.
- **`Window Manager` (Tool 02)**: OS window positioning and focus control.
- **`File Manager` (Tool 03)**: Filesystem tools (`list_directory`, `read_file`, `create_file`, `edit_file`, `move_file`, `delete_file`).
- **`Clipboard` (Tool 05)**: System clipboard read and write.
- **`Notifications` (Tool 06)**: Native desktop system alerts.
- **`System Monitor` (Tool 07)**: CPU, RAM, disk, and listening port monitor.
- **`Device Control` (Tool 08)**: Audio volume, display brightness, and power states.

---

### Pillar 3: 👁️ Vision & Multimodal Perception
*Visual understanding of the user's screen, interfaces, diagrams, and digital assets.*

#### Core Perceptual Capabilities
- **Screenshot & Desktop Understanding**: High-resolution screen captures of full desktop, regions, or specific app windows.
- **UI Element Detection & Visual Grounding**: Identifying buttons, input fields, menus, and icons by visual bounding boxes.
- **Optical Character Recognition (OCR)**: Extracting structured text from scanned documents, receipts, screenshots, and terminal buffers.
- **Screen & Application State Monitoring**: Real-time change detection across active windows to trigger reactive events.
- **Accessibility Tree Understanding**: Inspecting OS and browser accessibility node hierarchies for precise semantic targeting.
- **Multi-Monitor Awareness**: Mapping displays, virtual desktops, and resolutions.

#### Mapped Tools
- **`Screen Capture` (Tool 04)**: Full desktop and window screenshot capture (`browser_screenshot` currently web-scoped).
- **`OCR` (Tool 20)**: Optical character recognition engine.
- **`Image Understanding` (Tool 41)**: Multimodal scene and diagram analysis.
- **`Image Generation` (Tool 42)**: Image and diagram asset synthesis.
- **`Image Editing` (Tool 43)**: Resizing, cropping, converting, and annotating images.

---

### Pillar 4: 🗣️ Voice & Conversational Interaction
*Natural, hands-free auditory communication enabling ambient co-pilot interaction.*

#### Core Acoustic Capabilities
- **Wake Word Detection**: Low-power local wake word trigger (*"Hey Cocoa"*).
- **Speech-to-Text (STT)**: High-accuracy streaming speech transcription with noise rejection.
- **Text-to-Speech (TTS)**: Natural voice synthesis with expressive cadence and persona matching.
- **Continuous Hands-Free Conversation**: Bidirectional voice sessions while walking, cooking, or driving.
- **Voice Interruption (Barge-In)**: Immediate pause when the user speaks while Cocoa is talking.
- **Voice Commands & Confirmations**: Quick verbal confirmations (*"Yes, send it"*, *"Cancel"*).
- **Spoken Notifications**: Audio alerts for high-priority events and completed background tasks.

#### Mapped Tools
- **`Audio Transcription` (Tool 44)**: Whisper-based audio file and note transcription.
- **`Text-to-Speech` (Tool 45)**: Natural speech output synthesis.
- **`Media Controller` (Tool 46)**: Audio playback control (pause, resume, volume).

---

### Pillar 5: 🌐 Web Intelligence & Research
*Live external world awareness, browser automation, and multi-source truth verification.*

#### Core Web Capabilities
- **Locked Multi-Provider Search**: Primary execution via Tavily, fallback strictly via DuckDuckGo.
- **Browser Automation**: Full Chromium session control (click, type, navigate, scroll, extract, download).
- **Webpage Reading & Cleaning**: Stripping ads, scripts, and clutter to extract clean Markdown and reader views.
- **Multi-Source Research & Fact Cross-Checking**: Comparing multiple independent web sources to verify claims.
- **Website & DOM Monitoring**: Background polling of web pages for visual or text changes.
- **Price & Availability Tracking**: Monitoring product pages, GPU cloud pricing, and flights.
- **Web Form Automation**: Navigating and filling multi-step web forms with user-approved parameters.

#### Mapped Tools
- **`Web Search` (Tool 09)**: Real-time search engine (`web_search`).
- **`Web Fetcher` (Tool 10)**: Fast URL extraction (`browser_extract`).
- **`Browser Control` (Tool 11)**: Interactive web session suite (`browser_open`, `browser_click`, `browser_type`, etc.).
- **`News` (Tool 12)**: Topic-specific headline and article synthesis.
- **`Weather` (Tool 13)**: Local weather lookups and precipitation alerts.
- **`Maps / Places` (Tool 14)**: Distance calculations, travel time, and place lookups.
- **`Web Monitor` (Tool 15)**: Background website availability and change poller.
- **`Price Tracker` (Tool 39)**: Product price history and drop detector.
- **`Shopping Research` (Tool 40)**: Product value comparison and review synthesis.

---

### Pillar 6: 📚 Knowledge, Documents & Memory
*Deep codebase comprehension, document parsing, and persistent personal knowledge base.*

#### Core Knowledge Capabilities
- **Project RAG**: Structural AST chunking across 12 programming languages stored in PostgreSQL + pgvector.
- **Document Understanding**: Parsing PDFs, Word documents (.docx), ePubs, and Markdown files.
- **Spreadsheet Querying**: Reading, calculating, and modifying CSV and Excel (.xlsx) workbooks.
- **Semantic Search**: Fast cosine similarity retrieval across personal notes and codebases.
- **Document Summarization**: Distilling 50-page reports into 3 actionable bullets.
- **Personal Knowledge Base**: Persistent vector-indexed personal thoughts, notes, and preferences.
- **Cross-Project Knowledge**: Carrying learnings and patterns across multiple workspace projects.

#### Mapped Tools
- **`Project RAG` (Tool 16)**: Codebase chunk retrieval (`project_rag`).
- **`Document Reader` (Tool 17)**: PDF, docx, and rich document parser.
- **`Document Generator` (Tool 18)**: Formatted PDF/Markdown report compiler.
- **`Spreadsheet Tool` (Tool 19)**: CSV and Excel workbook analyst.
- **`Knowledge Memory` (Tool 21)**: Persistent user memory (`agent_memory`).
- **`Summarizer` (Tool 22)**: Long-form text and transcript summarizer.

---

### Pillar 7: 📅 Personal Assistant & Life Operations
*Daily executive support, personal logistics, communication, and friction removal.*

#### Core Assistant Capabilities
- **Schedule & Calendar Management**: Event scheduling, clash detection, and calendar synchronization.
- **Reminders & Nudges**: Proactive time-based and location-based nudges.
- **Todo & Task Prioritization**: Managing task lists and answering *"What's the easiest next step?"*.
- **Email Triage & Drafting**: Reading inboxes, flagging urgent emails, and drafting responses.
- **Contact & Relationship Context**: Remembering details about colleagues, friends, and family.
- **Personal Notes**: Syncing with local markdown vaults (Obsidian-compatible) and journals.
- **Meeting Assistant**: Ingesting meeting agendas, tracking discussion points, and noting action items.
- **Daily Briefings**: Morning 2-minute synthesis of the day's commitments, weather, and top news.
- **Habit & Routine Tracking**: Monitoring daily routines and consistency streaks.
- **Personal Economics**: Receipt categorization, budget burn rates, and currency conversion.

#### Mapped Tools
- **`Calendar` (Tool 23)**: Calendar event manager.
- **`Reminders` (Tool 24)**: Quick notification reminders.
- **`Tasks / Todo` (Tool 25)**: Personal task checklist.
- **`Email` (Tool 26)**: Email reading and draft dispatch.
- **`Contacts` (Tool 27)**: Personal address book context.
- **`Notes` (Tool 28)**: Personal markdown journal and notes vault.
- **`Habit Tracker` (Tool 29)**: Habit consistency tracker.
- **`Messaging` (Tool 31)**: Personal direct messaging.
- **`Slack / Teams` (Tool 32)**: Workplace chat integration.
- **`Discord` (Tool 33)**: Discord bot and channel integration.
- **`Social Publisher` (Tool 34)**: Social media post scheduler.
- **`Meeting Assistant` (Tool 35)**: Meeting transcript and action item taker.
- **`Expense Tracker` (Tool 36)**: Receipt and expense categorizer.
- **`Budget Analyzer` (Tool 37)**: Budget burn rate calculator.
- **`Currency Converter` (Tool 38)**: Foreign exchange rate calculator.

---

## 3. Existing Tools Mapped into the 7 Pillars

| Existing Cocoa Tool | Current Code Location | Assigned Pillar |
|---|---|---|
| `terminal` | `core/tools/terminal.py` | **Pillar 1: Core Intelligence & Agency** (Code Executor) |
| `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show`, `git_remote` | `core/tools/git.py` | **Pillar 1: Core Intelligence & Agency** (Git Tool) |
| `scheduler` | `core/scheduler_manager.py` | **Pillar 1: Core Intelligence & Agency** (Scheduler) |
| `list_directory`, `search_files`, `read_file`, `inspect_file`, `create_file`, `edit_file`, `move_file`, `delete_file` | `core/filesystem/tools.py` | **Pillar 2: Computer Control & OS** (File Manager) |
| `browser_screenshot` | `core/browser/tools.py` | **Pillar 3: Vision & Perception** (Screen Capture - Web) |
| `web_search` | `core/research/providers/router.py` | **Pillar 5: Web Intelligence** (Web Search - Tavily/DDG) |
| `browser_extract` | `core/browser/tools.py` | **Pillar 5: Web Intelligence** (Web Fetcher) |
| `browser_open`, `browser_navigate`, `browser_back`, `browser_click`, `browser_type`, `browser_scroll`, `browser_download`, `browser_close` | `core/browser/tools.py` | **Pillar 5: Web Intelligence** (Browser Control) |
| `project_rag` | `core/rag/retriever.py` | **Pillar 6: Knowledge & Documents** (Project RAG) |
| `agent_memory` | `core/memory.py` | **Pillar 6: Knowledge & Documents** (Knowledge Memory) |

---

## 4. Permission Governance Model

Across all 7 pillars, tool execution conforms strictly to the 4-tier safety model:

1. **`READ`** (Zero Friction): File reading, search, calendar inspection, system telemetry.
2. **`LOW_RISK_WRITE`** (Local Workspace): Creating personal notes, scratch files, local clipboard copy.
3. **`EXTERNAL_ACTION`** (User Verification): Sending emails, posting to Slack/Discord, submitting web forms.
4. **`HIGH_IMPACT_ACTION`** (Mandatory Approval Gate): Deleting files, financial transactions, modifying system device states.

---

## 5. Architectural Commitment

- **Zero Mock Tools Added**: No mock tools or placeholder scripts were implemented.
- **Decoupled Architecture**: Cocoa's tool layer remains completely model-independent (Hugging Face currently active).
- **Locked Providers**: Tavily Primary $\rightarrow$ DuckDuckGo Fallback is locked.
- **Database**: PostgreSQL + pgvector project isolation is locked.
- **Status**: The **7-Pillar Architecture** is the canonical foundation for all future Cocoa agent development.
