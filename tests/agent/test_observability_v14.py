"""
tests.test_observability_v14 — Comprehensive Test Suite for Kora Observability & Agent Replay (V14).

Covers:
  1. Agent Tracing & State Transitions
  2. Structured Event Stream & Chronological Ordering
  3. Normalized Error System across Components
  4. Performance Metrics & Latency Telemetry
  5. Read-Only Agent Replay Snapshots & Step Fidelity
  6. Root-Cause Failure Diagnostic Engine
  7. Sensitive Data Redaction across Traces, Errors, and Events
  8. Component Health Checks & System Readiness Probes
  9. Concurrent Trace Isolation
"""

from __future__ import annotations

import uuid
import pytest

from observability.diagnostics import DiagnosticEngine
from observability.errors import ErrorNormalizer
from observability.health import HealthMonitor
from observability.replay import AgentReplayEngine
from observability.sanitizer import mask_sensitive_text, sanitize_payload
from observability.tracer import AgentTracer
from observability.types import (
    AgentState,
    ComponentType,
    ErrorSeverity,
    EventType,
    HealthStatus,
    NormalizedError,
    StructuredEvent,
    TraceRecord,
)


# ── 1. Agent Tracing & Event Stream Tests ─────────────────────────────────────

class TestAgentTracingAndEvents:
    """Verify trace lifecycle, event emission, state transitions, and ordering."""

    def test_trace_lifecycle_and_state_transitions(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()

        # Start trace
        trace = tracer.start_trace(trace_id=trace_id, model="qwen-chat")
        assert trace.trace_id == trace_id
        assert trace.state == AgentState.PLANNING
        assert len(trace.events) == 1
        assert trace.events[0].event_type == EventType.REQUEST_RECEIVED

        # Record planning event
        tracer.record_event(trace_id, EventType.PLANNING_STARTED, ComponentType.AGENT_CORE, duration_ms=25)
        assert trace.state == AgentState.PLANNING

        # Record context retrieval
        tracer.record_event(trace_id, EventType.CONTEXT_RETRIEVED, ComponentType.RAG, duration_ms=60)
        assert trace.state == AgentState.RETRIEVING

        # Record tool execution
        tracer.record_event(
            trace_id,
            EventType.TOOL_STARTED,
            ComponentType.TOOLS,
            payload={"tool_name": "file_reader"},
        )
        assert trace.state == AgentState.EXECUTING_TOOL

        # Record verification
        tracer.record_event(
            trace_id,
            EventType.VERIFICATION_STARTED,
            ComponentType.AGENT_CORE,
        )
        assert trace.state == AgentState.VERIFYING

    @pytest.mark.asyncio
    async def test_trace_finish_and_telemetry(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()
        tracer.start_trace(trace_id=trace_id, model="qwen-chat")

        tracer.record_event(trace_id, EventType.TOOL_COMPLETED, ComponentType.TOOLS, duration_ms=100)

        completed = await tracer.finish_trace(trace_id=trace_id, status="success", verification_result="pass")
        assert completed.final_status == "success"
        assert completed.state == AgentState.COMPLETED
        assert completed.completed_at is not None
        assert completed.metrics is not None
        assert completed.metrics.tool_latency_ms == 100

    def test_event_chronological_ordering(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()
        tracer.start_trace(trace_id=trace_id)

        ev1 = tracer.record_event(trace_id, EventType.PLANNING_STARTED)
        ev2 = tracer.record_event(trace_id, EventType.CONTEXT_RETRIEVED)
        ev3 = tracer.record_event(trace_id, EventType.TOOL_STARTED)

        trace = tracer.get_trace(trace_id)
        assert trace is not None
        event_types = [e.event_type for e in trace.events]
        assert event_types == [
            EventType.REQUEST_RECEIVED,
            EventType.PLANNING_STARTED,
            EventType.CONTEXT_RETRIEVED,
            EventType.TOOL_STARTED,
        ]
        assert ev1.timestamp <= ev2.timestamp <= ev3.timestamp

    def test_concurrent_trace_isolation(self) -> None:
        tracer = AgentTracer()
        t1_id = uuid.uuid4()
        t2_id = uuid.uuid4()

        tracer.start_trace(trace_id=t1_id, model="model-1")
        tracer.start_trace(trace_id=t2_id, model="model-2")

        tracer.record_event(t1_id, EventType.TOOL_STARTED, payload={"tool": "tool-1"})
        tracer.record_event(t2_id, EventType.TOOL_STARTED, payload={"tool": "tool-2"})

        t1 = tracer.get_trace(t1_id)
        t2 = tracer.get_trace(t2_id)
        assert t1 is not None and t2 is not None

        t1_tools = [e.payload.get("tool") for e in t1.events if "tool" in e.payload]
        t2_tools = [e.payload.get("tool") for e in t2.events if "tool" in e.payload]

        assert t1_tools == ["tool-1"]
        assert t2_tools == ["tool-2"]


# ── 2. Normalized Error System Tests ──────────────────────────────────────────

class TestErrorNormalization:
    """Verify error standardization, severity assignment, and error codes."""

    def test_error_normalization_across_components(self) -> None:
        components = [
            (ComponentType.RAG, TimeoutError("RAG query timed out after 5s"), "ERR_RAG_TIMEOUT"),
            (ComponentType.TOOLS, PermissionError("Access denied on file"), "ERR_TOOLS_PERMISSION_DENIED"),
            (ComponentType.MODELS, Exception("Rate limit exceeded"), "ERR_MODELS_RATE_LIMIT"),
            (ComponentType.DATABASE, ConnectionError("Database unreachable"), "ERR_DATABASE_CONNECTION_FAILED"),
            (ComponentType.AUTOMATION, ValueError("Invalid cron syntax"), "ERR_AUTOMATION_PARSE_ERROR"),
        ]

        for comp, exc, expected_code in components:
            norm_err = ErrorNormalizer.normalize(exc, component=comp)
            assert norm_err.component == comp
            assert norm_err.error_code == expected_code
            assert norm_err.severity == ErrorSeverity.ERROR
            assert str(exc) in norm_err.message

    def test_custom_error_code_and_severity(self) -> None:
        norm_err = ErrorNormalizer.normalize(
            "Custom warning in research engine",
            component=ComponentType.WEB_RESEARCH,
            severity=ErrorSeverity.WARNING,
            custom_code="ERR_CUSTOM_RESEARCH_WARN",
        )
        assert norm_err.error_code == "ERR_CUSTOM_RESEARCH_WARN"
        assert norm_err.severity == ErrorSeverity.WARNING


# ── 3. Sensitive Data Redaction Tests ─────────────────────────────────────────

class TestSensitiveDataRedaction:
    """Verify masking of secrets, API keys, tokens, and private keys."""

    def test_secret_and_token_redaction(self) -> None:
        sensitive_samples = [
            ("Connecting with apiKey='sk-ant-1234567890abcdef1234567890abcdef' now", "[REDACTED_SECRET]"),
            ("Using Bearer abcdef1234567890abcdef1234567890 token", "[REDACTED_SECRET]"),
            ("GitHub key: ghp_123456789012345678901234567890123456", "[REDACTED_SECRET]"),
            ("Password: password='super_secret_password_123'", "[REDACTED_SECRET]"),
        ]

        for raw_text, expected_mask in sensitive_samples:
            sanitized = mask_sensitive_text(raw_text)
            assert "sk-ant-" not in sanitized
            assert "ghp_" not in sanitized
            assert "super_secret" not in sanitized
            assert expected_mask in sanitized

    def test_nested_payload_sanitization(self) -> None:
        payload = {
            "user": "developer",
            "api_key": "sk-12345678901234567890123456789012",
            "auth": {
                "password": "my_secret_password",
                "nested_token": "bearer 1234567890abcdef1234567890abcdef",
            },
            "headers": ["User-Agent: Kora", "Cookie: session_token=1234567890abcdef"],
        }

        sanitized = sanitize_payload(payload)
        assert sanitized["api_key"] == "[REDACTED_SECRET]"
        assert sanitized["auth"]["password"] == "[REDACTED_SECRET]"
        assert "my_secret_password" not in str(sanitized)
        assert "sk-123" not in str(sanitized)


# ── 4. Agent Replay Engine Tests ──────────────────────────────────────────────

class TestAgentReplayEngine:
    """Verify read-only replay snapshot generation and step fidelity."""

    @pytest.mark.asyncio
    async def test_replay_snapshot_generation(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()
        tracer.start_trace(trace_id=trace_id, metadata={"message": "Analyze code architecture"})

        tracer.record_event(
            trace_id,
            EventType.PLANNING_STARTED,
            ComponentType.AGENT_CORE,
            duration_ms=30,
            payload={"plan_summary": "1. Retrieve code, 2. Run AST analyzer"},
        )
        tracer.record_event(
            trace_id,
            EventType.CONTEXT_RETRIEVED,
            ComponentType.RAG,
            duration_ms=45,
            payload={"chunks": ["chunk_1", "chunk_2"]},
        )
        tracer.record_event(
            trace_id,
            EventType.TOOL_COMPLETED,
            ComponentType.TOOLS,
            duration_ms=80,
            payload={"tool_name": "code_analyzer", "output": "AST tree generated"},
        )
        tracer.record_event(
            trace_id,
            EventType.VERIFICATION_COMPLETED,
            ComponentType.AGENT_CORE,
            payload={"verdict": "pass"},
        )

        await tracer.finish_trace(trace_id=trace_id, status="success", final_response="Analysis complete.")

        replay_engine = AgentReplayEngine(tracer)
        snapshot = replay_engine.generate_replay(trace_id)

        assert snapshot is not None
        assert snapshot.trace_id == trace_id
        assert snapshot.is_read_only is True
        assert snapshot.status == "success"
        assert len(snapshot.steps) >= 5

        step_types = [s.step_type for s in snapshot.steps]
        assert "request" in step_types
        assert "plan" in step_types
        assert "context" in step_types
        assert "tool_call" in step_types
        assert "verification" in step_types
        assert "response" in step_types


# ── 5. Diagnostic Engine Tests ────────────────────────────────────────────────

class TestDiagnosticEngine:
    """Verify root-cause classification and remediation recommendations."""

    def test_diagnostic_report_for_permission_denial(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()
        tracer.start_trace(trace_id=trace_id)

        tracer.record_error(
            trace_id,
            error="PermissionDenied: Interactive approval required to delete directory",
            component=ComponentType.TOOLS,
        )

        diagnostic_engine = DiagnosticEngine(tracer)
        report = diagnostic_engine.diagnose_trace(trace_id)

        assert report is not None
        assert "Permission Gate" in report.root_cause
        assert "authorization" in report.suggested_fix.lower()

    def test_diagnostic_report_for_rag_timeout(self) -> None:
        tracer = AgentTracer()
        trace_id = uuid.uuid4()
        tracer.start_trace(trace_id=trace_id)

        tracer.record_error(
            trace_id,
            error="TimeoutError: RAG embedding lookup exceeded 10000ms deadline",
            component=ComponentType.RAG,
        )

        diagnostic_engine = DiagnosticEngine(tracer)
        report = diagnostic_engine.diagnose_trace(trace_id)

        assert report is not None
        assert report.error_code == "ERR_RAG_TIMEOUT"
        assert "deadline" in report.root_cause.lower()
        assert "re-index" in report.suggested_fix.lower() or "timeout" in report.suggested_fix.lower()


# ── 6. Component Health Probes Tests ──────────────────────────────────────────

class TestComponentHealthProbes:
    """Verify subsystem health monitoring and readiness aggregation."""

    @pytest.mark.asyncio
    async def test_system_health_report(self) -> None:
        monitor = HealthMonitor()
        report = await monitor.check_all()

        assert report.overall_status == HealthStatus.HEALTHY
        assert "database" in report.components
        assert "rag" in report.components
        assert "memory" in report.components
        assert "web_research" in report.components
        assert "models" in report.components
        assert "tools" in report.components
        assert "automation" in report.components
        assert "websocket" in report.components

        for comp_name, comp_health in report.components.items():
            assert comp_health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            assert comp_health.latency_ms >= 0
