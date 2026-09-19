"""
orchestration.messages — Structured Inter-Agent Communication (V16)

Defines strongly-typed message envelopes exchanged between the Coordinator and Sub-Agents.
Enforces structured inputs/outputs and eliminates unstructured side-channel communications.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TaskDispatchMessage:
    """Message sent by Coordinator to dispatch a sub-task to a specialized sub-agent."""
    task_id: str
    sender: str
    receiver: str
    objective: str
    context_package: dict[str, Any] = field(default_factory=dict)
    dependency_outputs: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    timeout_seconds: int = 60
    run_id: str | None = None
    message_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskResultMessage:
    """Message returned by a Sub-Agent to Coordinator containing execution results."""
    task_id: str
    sender: str
    receiver: str
    status: str  # 'completed', 'failed', 'timeout', 'cancelled'
    result: str = ""
    structured_output: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    duration_ms: int = 0
    tokens_used: int = 0
    error: str | None = None
    run_id: str | None = None
    message_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
