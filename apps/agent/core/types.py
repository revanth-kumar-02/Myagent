"""
core.types — Shared type definitions for the agent core loop.

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


@dataclass
class WebSource:
    url: str
    title: str
    snippet: str


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
    token_budget: int
    token_used: int = 0
