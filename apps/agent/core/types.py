"""
core.types — Shared type definitions for the agent core loop (RAG V7).

All components communicate through these typed dataclasses.
No business logic lives here.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any


# ── Enumerations ──────────────────────────────────────────────────────────────

class ActionType(str, enum.Enum):
    """Possible action types a planner step can resolve to."""
    RAG_QUERY       = "rag_query"
    WEB_RESEARCH    = "web_research"
    MEMORY_QUERY    = "memory_query"
    TOOL_CALL       = "tool_call"
    MODEL_GENERATE  = "model_generate"


class IntentType(str, enum.Enum):
    """Classifies the primary intent of the user request."""
    GENERAL_CONVERSATION = "general_conversation"  # Greetings, small talk, direct math
    KNOWLEDGE_RAG        = "knowledge_rag"         # Codebase, documents, project files
    MEMORY               = "memory"                # User preferences, past decisions, profile
    WEB_RESEARCH         = "web_research"          # Live web searches, current external information
    TOOL_ACTION          = "tool_action"           # Direct tool execution (file edits, terminal, etc.)
    MULTI_STEP_TASK      = "multi_step_task"       # Complex tasks requiring multiple sequential actions
    MIXED_REQUEST        = "mixed_request"         # Requests spanning multiple domains (e.g. RAG + Web)


class ContextNeed(str, enum.Enum):
    """Determines exact context retrieval sources needed."""
    NONE            = "none"
    RAG             = "rag"
    MEMORY          = "memory"
    WEB             = "web"
    RAG_AND_MEMORY  = "rag_and_memory"
    RAG_AND_WEB     = "rag_and_web"
    MEMORY_AND_WEB  = "memory_and_web"
    ALL             = "all"


class VerifierVerdict(str, enum.Enum):
    PASS      = "pass"
    RETRY     = "retry"
    ESCALATE  = "escalate"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"
    SKIPPED = "skipped"


class SourceType(str, enum.Enum):
    """Origin of a retrieved context item."""
    RAG     = "rag"
    MEMORY  = "memory"
    WEB     = "web"
    GRAPH   = "graph"
    USER    = "user"
    SYSTEM  = "system"


# ── Request / Response ────────────────────────────────────────────────────────

@dataclass
class ChatRequest:
    message: str
    session_id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID | None = None
    attachments: list[str] = field(default_factory=list)
    trace_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Source:
    chunk_id: uuid.UUID
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    page: int | None = None
    sheet: str | None = None
    slide: int | None = None
    score: float | None = None


@dataclass
class WebSource:
    url: str
    title: str
    snippet: str
    score: float | None = None


@dataclass
class GraphEvidence:
    source_entity: str
    relationship_type: str
    target_entity: str
    confidence: float = 1.0
    provenance_source: str = ""
    is_inferred: bool = False
    evidence_text: str = ""


@dataclass
class ContextItem:
    """Individual item in the assembled context package."""
    content: str
    source_type: SourceType
    score: float = 0.0
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    page: int | None = None
    sheet: str | None = None
    slide: int | None = None
    url: str | None = None
    title: str | None = None
    chunk_id: uuid.UUID | None = None


@dataclass
class AgentContextPackage:
    """Unified bounded context package across RAG, Memory, Web, and Graph."""
    items: list[ContextItem] = field(default_factory=list)
    rag_sources: list[Source] = field(default_factory=list)
    web_sources: list[WebSource] = field(default_factory=list)
    graph_evidence: list[GraphEvidence] = field(default_factory=list)
    formatted_text: str = ""
    token_count: int = 0
    resolved_sources: set[SourceType] = field(default_factory=set)



@dataclass
class ChatResponse:
    full_text: str
    sources: list[Source] = field(default_factory=list)
    web_sources: list[WebSource] = field(default_factory=list)
    model_used: str = "qwen-chat"
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


@dataclass
class AgentResponse:
    """Rich grounded response returned by the Decision Engine."""
    content: str
    sources: list[Source] = field(default_factory=list)
    web_sources: list[WebSource] = field(default_factory=list)
    action_status: str = "success"
    limitations: list[str] = field(default_factory=list)
    tokens_used: int = 0
    model_used: str = "qwen-chat"


# ── Decision & Planning ────────────────────────────────────────────────────────

@dataclass
class StepDecision:
    """Evaluation result for an individual plan step."""
    action_type: ActionType
    goal: str
    rationale: str
    target_tool: str | None = None
    target_capability: str = "chat"
    requires_permission: bool = False
    requires_verification: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    index: int
    label: str
    action_type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    goal: str = ""
    required_context: list[SourceType] = field(default_factory=list)
    required_tool: str | None = None
    dependencies: list[int] = field(default_factory=list)
    expected_result: str = ""
    verification_method: str = "default_check"
    status: StepStatus = StepStatus.PENDING


@dataclass
class Plan:
    steps: list[PlanStep]
    trace_id: uuid.UUID
    is_replan: bool = False
    replan_reason: str | None = None


# ── Execution & Verification ──────────────────────────────────────────────────

@dataclass
class ExecutorResult:
    step: PlanStep
    success: bool
    content: str          # serialised result for context assembly
    raw: Any = None       # typed result (RAGContext, ToolResult, etc.)
    error: str | None = None


@dataclass
class ExecutionReport:
    """Summary of step execution and verification outcome."""
    step_index: int
    success: bool
    output: str
    verdict: VerifierVerdict
    error_message: str | None = None
    retries_used: int = 0


# ── Context ───────────────────────────────────────────────────────────────────

@dataclass
class ContextWindow:
    """The bounded context passed to every model call."""
    system_prompt: str
    history: list[dict[str, str]]    # [{"role": ..., "content": ...}]
    rag_context: str
    tool_history: list[dict[str, Any]]
    memory_context: str
    web_context: str = ""
    token_budget: int = 8192
    token_used: int = 0
    package: AgentContextPackage | None = None
