"""
observability.tracing — Request Tracing

Propagates trace_id through all agent steps.
Writes completed traces to agent_traces table.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, TYPE_CHECKING

import structlog
import structlog.contextvars

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def trace_step(
    step: str,
    session_id: uuid.UUID | None = None,
    trace_id: uuid.UUID | None = None,
    model: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Context manager that times a step, binds trace_id to structlog context,
    and yields a mutable metadata dict that callers populate with token counts etc.

    Usage:
        async with trace_step("planner", session_id=sid, trace_id=tid) as meta:
            meta["input_tokens"] = 42
            result = await planner.plan(...)
    """
    tid = trace_id or uuid.uuid4()
    structlog.contextvars.bind_contextvars(trace_id=str(tid), step=step)
    start = time.monotonic()
    meta: dict[str, Any] = {"step": step, "session_id": session_id, "trace_id": tid, "model": model}

    try:
        yield meta
    finally:
        meta["latency_ms"] = int((time.monotonic() - start) * 1000)
        structlog.contextvars.unbind_contextvars("trace_id", "step")

        # TODO: persist meta to agent_traces in feature phase
