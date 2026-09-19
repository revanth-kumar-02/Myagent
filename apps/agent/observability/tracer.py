"""
observability.tracer — High-Fidelity Agent Execution Tracer & Telemetry Engine (V14).

Manages trace lifecycles, structured event streams, latency breakdowns, and PostgreSQL persistence.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from db.schema import (
    AgentError as DBAgentError,
    AgentEvent as DBAgentEvent,
    AgentTrace as DBAgentTrace,
)
from observability.errors import ErrorNormalizer
from observability.sanitizer import sanitize_payload
from observability.types import (
    AgentState,
    ComponentType,
    ErrorSeverity,
    EventType,
    NormalizedError,
    PerformanceMetrics,
    StructuredEvent,
    TraceRecord,
)

logger = structlog.get_logger(__name__)


class AgentTracer:
    """
    Central Tracer managing end-to-end execution observability and telemetry.
    """

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self._db = db_session
        self._active_traces: dict[uuid.UUID, TraceRecord] = {}
        self._completed_traces: dict[uuid.UUID, TraceRecord] = {}
        self._start_times: dict[uuid.UUID, float] = {}

    # ── Trace Lifecycle ──────────────────────────────────────────────────────

    def start_trace(
        self,
        trace_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceRecord:
        """
        Initialize a new execution trace.
        """
        tid = trace_id or uuid.uuid4()
        sanitized_meta = sanitize_payload(metadata or {})

        record = TraceRecord(
            trace_id=tid,
            task_id=task_id,
            session_id=session_id,
            project_id=project_id,
            state=AgentState.PLANNING,
            model=model,
            metadata=sanitized_meta,
        )

        self._active_traces[tid] = record
        self._start_times[tid] = time.monotonic()

        # Emit initial request event
        self.record_event(
            trace_id=tid,
            event_type=EventType.REQUEST_RECEIVED,
            component=ComponentType.AGENT_CORE,
            payload={"session_id": str(session_id) if session_id else None, "project_id": str(project_id) if project_id else None},
        )

        logger.info("agent_trace_started", trace_id=str(tid), model=model)
        return record

    def record_event(
        self,
        trace_id: uuid.UUID,
        event_type: EventType | str,
        component: ComponentType | str = ComponentType.AGENT_CORE,
        status: str = "info",
        duration_ms: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> StructuredEvent:
        """
        Record a structured lifecycle event in the trace stream.
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        if isinstance(component, str):
            component = ComponentType(component)

        sanitized_payload = sanitize_payload(payload or {})

        event = StructuredEvent(
            event_type=event_type,
            component=component,
            trace_id=trace_id,
            status=status,
            duration_ms=duration_ms,
            payload=sanitized_payload,
        )

        trace = self._active_traces.get(trace_id) or self._completed_traces.get(trace_id)
        if trace is not None:
            trace.events.append(event)
            # Update state based on event
            self._update_trace_state(trace, event_type)

        logger.debug(
            "structured_event_recorded",
            trace_id=str(trace_id),
            event_type=event_type.value,
            component=component.value,
            duration_ms=duration_ms,
        )
        return event

    def record_error(
        self,
        trace_id: uuid.UUID,
        error: Exception | str | dict[str, Any],
        component: ComponentType | str = ComponentType.AGENT_CORE,
        severity: ErrorSeverity | str = ErrorSeverity.ERROR,
        custom_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> NormalizedError:
        """
        Normalize and record an execution error.
        """
        norm_err = ErrorNormalizer.normalize(
            error=error,
            component=component,
            trace_id=trace_id,
            severity=severity,
            custom_code=custom_code,
            details=details,
        )

        trace = self._active_traces.get(trace_id) or self._completed_traces.get(trace_id)
        if trace is not None:
            trace.errors.append(norm_err)
            trace.error = norm_err.message

        return norm_err

    async def finish_trace(
        self,
        trace_id: uuid.UUID,
        status: str = "success",
        verification_result: str = "pass",
        final_response: str | None = None,
        error: str | None = None,
    ) -> TraceRecord:
        """
        Conclude trace, calculate telemetry metrics, and persist to database.
        """
        trace = self._active_traces.pop(trace_id, None)
        if trace is None:
            trace = self._completed_traces.get(trace_id)
            if trace is None:
                trace = TraceRecord(trace_id=trace_id)

        start_time = self._start_times.pop(trace_id, time.monotonic())
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        trace.completed_at = datetime.now(timezone.utc)
        trace.duration_ms = elapsed_ms
        trace.final_status = status
        trace.verification_result = verification_result
        trace.state = AgentState.COMPLETED if status == "success" else AgentState.FAILED
        if error:
            trace.error = error

        # Emit completion / failure event
        final_event = EventType.TASK_COMPLETED if status == "success" else EventType.TASK_FAILED
        self.record_event(
            trace_id=trace_id,
            event_type=final_event,
            component=ComponentType.AGENT_CORE,
            status="success" if status == "success" else "error",
            duration_ms=elapsed_ms,
            payload={"final_status": status, "verification_result": verification_result},
        )

        # Compute Performance Metrics
        trace.metrics = self._calculate_metrics(trace)
        self._completed_traces[trace_id] = trace

        # Persist to PostgreSQL if session is active
        if self._db is not None:
            try:
                db_trace = DBAgentTrace(
                    trace_id=trace.trace_id,
                    session_id=trace.session_id,
                    step=trace.final_status,
                    model=trace.model,
                    input_tokens=trace.metrics.input_tokens,
                    output_tokens=trace.metrics.output_tokens,
                    latency_ms=trace.duration_ms,
                    metadata_={
                        "tools_used": trace.tools_used,
                        "verification_result": trace.verification_result,
                        "events_count": len(trace.events),
                        "errors_count": len(trace.errors),
                    },
                )
                self._db.add(db_trace)

                for ev in trace.events:
                    db_ev = DBAgentEvent(
                        trace_id=ev.trace_id,
                        event_type=ev.event_type.value,
                        component=ev.component.value,
                        status=ev.status,
                        duration_ms=ev.duration_ms,
                        payload=ev.payload,
                    )
                    self._db.add(db_ev)

                for err in trace.errors:
                    db_err = DBAgentError(
                        trace_id=err.trace_id,
                        error_code=err.error_code,
                        component=err.component.value,
                        message=err.message,
                        severity=err.severity.value,
                        details=err.details,
                    )
                    self._db.add(db_err)

                await self._db.flush()
            except Exception as exc:
                logger.warning("trace_persistence_failed", error=str(exc))

        logger.info(
            "agent_trace_completed",
            trace_id=str(trace_id),
            duration_ms=elapsed_ms,
            status=status,
            events_count=len(trace.events),
            errors_count=len(trace.errors),
        )
        return trace

    # ── Retrieval & Diagnostics ──────────────────────────────────────────────

    def get_trace(self, trace_id: uuid.UUID) -> TraceRecord | None:
        """Retrieve trace record from active or completed store."""
        return self._active_traces.get(trace_id) or self._completed_traces.get(trace_id)

    def list_traces(
        self,
        project_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[TraceRecord]:
        """List historical traces filtered by project or session."""
        all_traces = list(self._completed_traces.values()) + list(self._active_traces.values())
        filtered: list[TraceRecord] = []

        for t in all_traces:
            if project_id is not None and t.project_id is not None and t.project_id != project_id:
                continue
            if session_id is not None and t.session_id is not None and t.session_id != session_id:
                continue
            filtered.append(t)
            if len(filtered) >= limit:
                break

        filtered.sort(key=lambda x: x.created_at, reverse=True)
        return filtered

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _update_trace_state(self, trace: TraceRecord, event_type: EventType) -> None:
        """Map event type to agent state."""
        state_map = {
            EventType.PLANNING_STARTED: AgentState.PLANNING,
            EventType.CONTEXT_RETRIEVED: AgentState.RETRIEVING,
            EventType.TOOL_STARTED: AgentState.EXECUTING_TOOL,
            EventType.VERIFICATION_STARTED: AgentState.VERIFYING,
            EventType.REPLANNING: AgentState.REPLANNING,
            EventType.TASK_COMPLETED: AgentState.COMPLETED,
            EventType.TASK_FAILED: AgentState.FAILED,
        }
        if event_type in state_map:
            trace.state = state_map[event_type]

    def _calculate_metrics(self, trace: TraceRecord) -> PerformanceMetrics:
        """Aggregate event durations into categorized performance metrics."""
        model_lat = 0
        retrieval_lat = 0
        tool_lat = 0
        retries = 0

        for ev in trace.events:
            if ev.component == ComponentType.MODELS:
                model_lat += ev.duration_ms
            elif ev.component in (ComponentType.RAG, ComponentType.MEMORY, ComponentType.WEB_RESEARCH):
                retrieval_lat += ev.duration_ms
            elif ev.component == ComponentType.TOOLS:
                tool_lat += ev.duration_ms
            if ev.event_type == EventType.REPLANNING:
                retries += 1

        failure_rate = 1.0 if trace.final_status == "failed" else 0.0

        return PerformanceMetrics(
            trace_id=trace.trace_id,
            model_latency_ms=model_lat,
            retrieval_latency_ms=retrieval_lat,
            tool_latency_ms=tool_lat,
            total_duration_ms=trace.duration_ms,
            input_tokens=trace.metadata.get("input_tokens", 0),
            output_tokens=trace.metadata.get("output_tokens", 0),
            retry_count=retries,
            failure_rate=failure_rate,
        )
