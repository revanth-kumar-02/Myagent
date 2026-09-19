"""
orchestration.types — Data Types, Schemas, and Enums for Kora Multi-Agent Orchestration (V16).

Defines:
  - Specialized agent types & capability profiles
  - TaskGraph nodes, dependencies, and execution states
  - Inter-agent message envelopes
  - Synthesis, provenance, and contradiction detection schemas
  - Orchestrator safety and concurrency configurations
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class AgentType(str, enum.Enum):
    """Specialized agent types supported in Kora's multi-agent system."""
    COORDINATOR        = "coordinator"
    RESEARCH_AGENT     = "research_agent"
    CODING_AGENT       = "coding_agent"
    DATA_AGENT         = "data_agent"
    BROWSER_AGENT      = "browser_agent"
    DOCUMENT_AGENT     = "document_agent"
    GENERAL_TASK_AGENT = "general_task_agent"


class NodeStatus(str, enum.Enum):
    """Execution status of an individual task node in the DAG."""
    PENDING   = "pending"
    READY     = "ready"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"
    TIMEOUT   = "timeout"


class GraphExecutionMode(str, enum.Enum):
    """Execution mode for task graph resolution."""
    SEQUENTIAL = "sequential"
    PARALLEL   = "parallel"
    HYBRID     = "hybrid"


@dataclass
class AgentProfile:
    """Capability specification and security boundary for a specialized agent."""
    agent_type: AgentType
    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    permission_limits: list[str] = field(default_factory=list)
    max_concurrency: int = 2
    system_prompt: str = ""
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if isinstance(self.agent_type, str):
            self.agent_type = AgentType(self.agent_type)


@dataclass
class TaskNode:
    """Individual node in the task graph DAG representing a sub-agent task."""
    node_id: str
    agent_type: AgentType
    objective: str
    dependencies: list[str] = field(default_factory=list)
    input_data: dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    result: str = ""
    structured_output: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None
    timeout_seconds: int = 60
    retry_count: int = 0
    delegation_depth: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.agent_type, str):
            self.agent_type = AgentType(self.agent_type)
        if isinstance(self.status, str):
            self.status = NodeStatus(self.status)


@dataclass
class ContradictionReport:
    """Analysis of conflicting claims between multiple sub-agent results."""
    detected: bool = False
    conflicting_nodes: list[str] = field(default_factory=list)
    claim_a: str = ""
    claim_b: str = ""
    resolution: str = ""
    confidence: float = 1.0


@dataclass
class SynthesizedResult:
    """Final unified result produced by the Coordinator from all sub-agents."""
    summary: str
    full_text: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    web_sources: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)  # node_id -> agent_type/source
    nodes_executed: list[str] = field(default_factory=list)
    contradictions: list[ContradictionReport] = field(default_factory=list)
    duration_ms: int = 0
    tokens_used: int = 0
    status: str = "success"  # 'success', 'partial_success', 'failed'


@dataclass
class OrchestratorConfig:
    """Configuration settings and security constraints for Multi-Agent Orchestration."""
    max_concurrent_agents: int = 4
    max_delegation_depth: int = 2
    default_task_timeout_seconds: int = 60
    allow_parallel_execution: bool = True
    strict_verification: bool = True
    enable_contradiction_detection: bool = True
    max_subagents_per_goal: int = 8
