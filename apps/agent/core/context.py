"""
core.context — Context Manager

Responsibilities:
  - Load session history from Redis
  - Load episodic memory from PostgreSQL
  - Assemble the bounded ContextWindow for each model call
  - Enforce token budget (truncate history before exceeding limit)
  - Persist session state back to Redis after each turn
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from core.types import ContextWindow

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are Kora, a RAG-first autonomous AI agent. You help users understand and work with
their projects, files, documents, and code. You always ground your responses in the
user's indexed project knowledge. When you use external web research, you cite it clearly
and separately from project sources. You are honest about uncertainty and never fabricate
information.
"""


class ContextManager:
    """
    Assembles and manages the bounded context window for a single agent session.

    Instantiated per-session (not per-turn) so session state persists in memory
    between turns within a session.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID | None,
        db: "AsyncSession",
        redis: "aioredis.Redis",
        token_budget: int = 8192,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self._db = db
        self._redis = redis
        self.token_budget = token_budget
        self._history: list[dict[str, str]] = []

    async def load(self) -> None:
        """Load history from Redis and memory from PostgreSQL."""
        raise NotImplementedError  # TODO: implement in feature phase

    def build(
        self,
        *,
        rag_context: str = "",
        memory_context: str = "",
        tool_history: list[dict] | None = None,
    ) -> ContextWindow:
        """
        Assemble the ContextWindow for the current turn.
        Truncates history from the oldest messages first if over token budget.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def append_user(self, message: str) -> None:
        """Add a user message to the in-memory history."""
        self._history.append({"role": "user", "content": message})

    async def append_assistant(self, message: str) -> None:
        """Add an assistant message to the in-memory history."""
        self._history.append({"role": "assistant", "content": message})

    async def save(self) -> None:
        """Persist current history to Redis."""
        raise NotImplementedError  # TODO: implement in feature phase
