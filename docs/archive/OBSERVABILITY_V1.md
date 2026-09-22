# Kora — V14: Observability, Diagnostics & Agent Replay

## 1. Purpose & Overview
The **Kora Observability & Agent Replay (V14)** subsystem provides end-to-end telemetry, structured event streams, normalized error categorization, performance metrics, read-only replay snapshots, root-cause diagnostic reports, and component health monitoring.

---

## 2. Core Architecture

```
User Request
     |
     v
+------------------+
|   AgentTracer    | ---> Persists to PostgreSQL (`agent_traces`, `agent_events`, `agent_errors`)
+------------------+
     |
     +---> Emits Structured Events (`request_received`, `planning_started`, etc.)
     +---> Tracks Latency (Models, RAG/Memory Retrieval, Tool Calls)
     +---> Sanitizes Credentials via `sanitize_payload`
     |
     v
+-----------------------+     +--------------------+     +-------------------+
|  AgentReplayEngine    |     |  DiagnosticEngine  |     |   HealthMonitor   |
| (Read-Only Playback)  |     | (Root-Cause Fixes) |     | (Component Probes)|
+-----------------------+     +--------------------+     +-------------------+
     |                                 |                           |
     +---------------------------------+---------------------------+
                                       |
                                       v
                     +-----------------------------------+
                     |    Flutter Desktop Debug UI       |
                     | (Timeline, Health, Error Center)  |
                     +-----------------------------------+
```

---

## 3. Structured Event Stream (`EventType`)
1. `request_received`: User query ingested with session/project context.
2. `planning_started`: Task decomposition into ordered plan steps.
3. `context_retrieved`: Retrieval from RAG, Memory, Web, or Graph.
4. `model_called`: Model inference invocation.
5. `tool_started`: Execution start of a tool.
6. `tool_completed`: Result output from tool execution.
7. `verification_started`: Verification of execution step.
8. `verification_completed`: Verification verdict (`pass`, `retry`, `escalate`).
9. `replanning`: Corrective plan adjustment triggered by failure.
10. `task_completed`: Successful task conclusion.
11. `task_failed`: Unrecoverable task failure.

---

## 4. Normalized Error System (`ErrorNormalizer`)
Errors across all subsystems are mapped to standardized records with error codes (`ERR_<COMPONENT>_<REASON>`), component tags, severity levels (`INFO`, `WARNING`, `ERROR`, `CRITICAL`), and sanitized messages:
- `ERR_RAG_TIMEOUT`, `ERR_RAG_PARSE_ERROR`
- `ERR_TOOL_PERMISSION_DENIED`, `ERR_TOOL_TIMEOUT`
- `ERR_MODEL_RATE_LIMIT`, `ERR_MODEL_UNAVAILABLE`
- `ERR_DB_CONNECTION_FAILED`, `ERR_AUTOMATION_SCHEDULE_FAILED`

---

## 5. Read-Only Agent Replay (`AgentReplayEngine`)
Reconstructs an immutable, sequential snapshot of historical execution:
`Request -> Plan -> Context -> Decisions -> Tools -> Results -> Verification -> Final Response`
The replay engine operates strictly read-only with zero execution side-effects.

---

## 6. Sensitive Data Redaction (`sanitizer.py`)
- Regex-based scanners automatically mask passwords, API keys (`sk-*`, `ghp_*`), bearer tokens, and private keys with `[REDACTED_SECRET]`.
- Excessive binary audio/image dumps are masked with `[REDACTED_BINARY]`.
- Redaction applies recursively across all trace events, errors, and structlog logs.
