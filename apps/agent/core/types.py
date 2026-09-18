"""
core.types — Shared type definitions for the agent core loop (RAG V4).

All components communicate through these typed dataclasses.
No business logic lives here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Enumerations ──────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    """Possible action types a planner step can resolve to."""
    RAG_QUERY       = "rag_query"
    WEB_RESEARCH    = "web_research"
    MEMORY_QUERY    = "memory_query"
    TOOL_CALL       = "tool_call"
    MODEL_GENERATE  = "model_generate"


class VerifierVerdict(str, Enum):
    PASS      = "pass"
    RETRY     = "retry"
    ESCALATE  = "escalate"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


class SourceType(str, Enum):
    """Origin of a retrieved context item."""
    RAG     = "rag"
    MEMORY  = "memory"
    WEB     = "web"
    USER    = "user"
    SYSTEM  = "system"


# ── Request / Response ────────────────────────────────────────────────────────

@dataclass
class ChatRequest:
    message: str
    session_id: uuid.UUID
    project_id: uuid.UUID | None
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
    """Unified bounded context package across RAG, Memory, and Web."""
    items: list[ContextItem] = field(default_factory=list)
    rag_sources: list[Source] = field(default_factory=list)
    web_sources: list[WebSource] = field(default_factory=list)
    formatted_text: str = ""
    token_count: int = 0
    resolved_sources: set[SourceType] = field(default_factory=set)


@dataclass
class ChatResponse:
    full_text: str
    sources: list[Source]
    web_sources: list[WebSource]
    model_used: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


# ── Planner ───────────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    index: int
    label: str
    action_type: ActionType
    params: dict[str, Any]
    status: StepStatus = StepStatus.PENDING


@dataclass
class Plan:
    steps: list[PlanStep]
    trace_id: uuid.UUID


# ── Executor ──────────────────────────────────────────────────────────────────

@dataclass
class ExecutorResult:
    step: PlanStep
    success: bool
    content: str          # serialised result for context assembly
    raw: Any = None       # typed result (RAGContext, ToolResult, etc.)
    error: str | None = None


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
