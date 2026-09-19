"""
observability.types — Data types and enumerations for Kora Observability & Replay (V14).

Defines:
  - Agent execution states and event lifecycle types
  - Normalized error schemas and severity levels
  - Telemetry and performance metrics
  - Read-only agent replay snapshots and step records
  - Diagnostics and system component health checks
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class AgentState(str, enum.Enum):
    """Current execution phase of the agent."""
    IDLE           = "idle"
    PLANNING       = "planning"
    RETRIEVING     = "retrieving"
    EXECUTING_TOOL = "executing_tool"
    VERIFYING      = "verifying"
    REPLANNING     = "replanning"
    COMPLETED      = "completed"
    FAILED         = "failed"


class EventType(str, enum.Enum):
    """Structured lifecycle events emitted during task execution."""
    REQUEST_RECEIVED       = "request_received"
    PLANNING_STARTED       = "planning_started"
    CONTEXT_RETRIEVED      = "context_retrieved"
    MODEL_CALLED           = "model_called"
    TOOL_STARTED           = "tool_started"
    TOOL_COMPLETED         = "tool_completed"
    VERIFICATION_STARTED   = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    REPLANNING             = "replanning"
    TASK_COMPLETED         = "task_completed"
    TASK_FAILED            = "task_failed"
    COORDINATOR_PLAN_STARTED = "coordinator_plan_started"
    SUBAGENT_DISPATCHED    = "subagent_dispatched"
    SUBAGENT_COMPLETED     = "subagent_completed"
    SUBAGENT_FAILED        = "subagent_failed"
    SYNTHESIS_STARTED      = "synthesis_started"
    SYNTHESIS_COMPLETED    = "synthesis_completed"


class ComponentType(str, enum.Enum):
    """Major architectural subsystems."""
    AGENT_CORE    = "agent_core"
    RAG           = "rag"
    MEMORY        = "memory"
    WEB_RESEARCH  = "web_research"
    MODELS        = "models"
    TOOLS         = "tools"
    DATABASE      = "database"
    AUTOMATION    = "automation"
    WEBSOCKET     = "websocket"
    MULTIMODAL    = "multimodal"
    PROACTIVE     = "proactive"
    ORCHESTRATION = "orchestration"



class ErrorSeverity(str, enum.Enum):
    """Severity classification for normalized errors."""
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"


class HealthStatus(str, enum.Enum):
    """Operational health state of a subsystem."""
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class StructuredEvent:
    """An individual structured event in the trace stream."""
    event_type: EventType
    component: ComponentType
    trace_id: uuid.UUID
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "info"  # 'info', 'success', 'warning', 'error'
    duration_ms: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)
        if isinstance(self.component, str):
            self.component = ComponentType(self.component)


@dataclass
class NormalizedError:
    """Normalized error record with component categorization and severity."""
    error_code: str
    component: ComponentType
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    trace_id: uuid.UUID | None = None
    error_id: uuid.UUID = field(default_factory=uuid.uuid4)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.component, str):
            self.component = ComponentType(self.component)
        if isinstance(self.severity, str):
            self.severity = ErrorSeverity(self.severity)


@dataclass
class PerformanceMetrics:
    """Performance and latency telemetry for an execution trace."""
    trace_id: uuid.UUID
    model_latency_ms: int = 0
    retrieval_latency_ms: int = 0
    tool_latency_ms: int = 0
    total_duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0
    failure_rate: float = 0.0
    cache_hits: int = 0


@dataclass
class TraceRecord:
    """Complete execution record persisted in PostgreSQL agent_traces."""
    trace_id: uuid.UUID = field(default_factory=uuid.uuid4)
    task_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    state: AgentState = AgentState.IDLE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: int = 0
    model: str | None = None
    retrieved_context_summary: str = ""
    tools_used: list[str] = field(default_factory=list)
    verification_result: str = "pass"
    final_status: str = "success"  # 'success', 'failed'
    error: str | None = None
    events: list[StructuredEvent] = field(default_factory=list)
    errors: list[NormalizedError] = field(default_factory=list)
    metrics: PerformanceMetrics | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayStep:
    """Individual action step in an execution replay."""
    step_index: int
    step_type: str  # 'request', 'plan', 'context', 'tool_call', 'verification', 'response'
    label: str
    input_payload: Any = None
    output_payload: Any = None
    tool_name: str | None = None
    duration_ms: int = 0
    verification_verdict: str = "pass"
    status: str = "done"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReplaySnapshot:
    """Immutable, read-only replay snapshot of a completed agent execution."""
    trace_id: uuid.UUID
    task_id: uuid.UUID | None
    user_request: str
    plan_summary: str
    context_summary: str
    steps: list[ReplayStep] = field(default_factory=list)
    final_response: str = ""
    duration_ms: int = 0
    status: str = "success"
    is_read_only: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiagnosticReport:
    """Structured diagnostic summary for troubleshooting failures."""
    trace_id: uuid.UUID
    error_code: str
    component: ComponentType
    root_cause: str
    failed_action: str
    suggested_fix: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ComponentHealth:
    """Operational health metrics of an individual component."""
    component: ComponentType
    status: HealthStatus = HealthStatus.HEALTHY
    latency_ms: int = 0
    message: str = "OK"
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SystemHealthReport:
    """Aggregated health report across all system components."""
    overall_status: HealthStatus
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
