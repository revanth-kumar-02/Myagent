# Kora — V14: Observability Verification & Test Report

## 1. Overview
This document records the verification matrix and test execution results for the **Kora Observability, Diagnostics & Agent Replay (V14)** subsystem.

---

## 2. Test Execution Matrix

The test suite [`tests/agent/test_observability_v14.py`](file:///home/rev/My_Personal_Space/Projects/Unfinished/Myagent/tests/agent/test_observability_v14.py) verifies all core capabilities:

| Test Group | Test Cases | Scope Verified |
| :--- | :--- | :--- |
| **Agent Tracing & Events** | `test_trace_lifecycle_and_state_transitions`<br>`test_structured_event_ordering`<br>`test_concurrent_trace_isolation` | Complete trace lifecycle (start, events, finish), state mapping, chronological event ordering, multi-tenant trace isolation. |
| **Error Normalization** | `test_error_normalization_across_components`<br>`test_error_code_classification` | Mapping exceptions to `NormalizedError`, severity assignment, standardized error codes (`ERR_TOOL_*`, `ERR_RAG_*`, etc.). |
| **Performance Telemetry** | `test_performance_metrics_aggregation` | Aggregating model latency, retrieval latency, tool duration, token consumption, and retry counts. |
| **Read-Only Replay** | `test_replay_snapshot_generation`<br>`test_replay_immutability_and_fidelity` | Reconstructing full execution snapshots (Request -> Plan -> Context -> Tool Calls -> Verification -> Response) with strict read-only guarantee. |
| **Root-Cause Diagnostics** | `test_diagnostic_report_for_tool_failure`<br>`test_diagnostic_report_for_permission_denial`<br>`test_diagnostic_report_for_rag_timeout` | Classifying failure modes and generating actionable remediation recommendations. |
| **Sensitive Data Redaction** | `test_secret_and_token_redaction`<br>`test_nested_payload_sanitization` | Masking passwords, API keys (`sk-*`, `ghp_*`), bearer tokens, and private keys (`[REDACTED_SECRET]`). |
| **Component Health Probes** | `test_component_health_probes`<br>`test_system_health_report` | Probing PostgreSQL, RAG, Memory, Web, Models, Tools, and WebSockets for health and latency. |

---

## 3. Verification Command
To run all tests:

```bash
PYTHONPATH=apps/agent pytest tests/agent/ -v
```
