# Kora Observability & Telemetry

Kora includes end-to-end tracing and structured logging for all agent actions, model calls, tool executions, and retrieval pipelines.

---

## 1. Structured Logging

Structured logging is powered by `structlog`. In development, logs format to colorized console outputs; in production, logs emit structured JSON Lines for aggregation.

---

## 2. Distributed Tracing & Span Storage

Traces are recorded per agent execution turn and persisted to PostgreSQL `agent_traces` table:
- `trace_id`: UUID correlating all steps within a turn.
- `session_id`: User session identifier.
- `step`: Specific action (e.g. `MODEL_ROUTE`, `RAG_RETRIEVE`, `TOOL_EXECUTION`).
- `duration_ms`: Execution latency for the step.
- `metadata`: Execution parameters and token consumption metrics.
