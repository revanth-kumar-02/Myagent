"""
core.context — Context Manager (RAG V4)

Responsibilities:
  - Load and manage active conversation history
  - Assemble the bounded ContextWindow for each model call
  - Enforce strict token budgeting with oldest-first history truncation
  - Ground responses by clearly distinguishing RAG facts, memories, and web research
  - Persist session state to Redis
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog
import tiktoken

from core.context_package import AgentContextPackage
from core.types import ContextWindow

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

_SYSTEM_PROMPT = """\
You are Kora, a RAG-first autonomous AI agent. You understand and work with user projects,
files, documents, spreadsheets, slides, and code through verified RAG context.

GROUNDING DIRECTIVES:
1. Always ground your answers about the project in the provided [RAG] context.
2. Distinguish verified project facts from external [WEB] research or user [MEMORY] preferences.
3. Cite exact file paths, line ranges, symbols, sheets, or slide numbers when referencing context.
4. If relevant information is not in the provided context, state clearly that it is not found.
5. Never hallucinate or fabricate facts claimed to come from the project.
"""


class ContextManager:
    """
    Assembles and manages the bounded context window for a single agent session.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID | None,
        db: "AsyncSession" | None = None,
        redis: "aioredis.Redis" | None = None,
        token_budget: int = 8192,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self._db = db
        self._redis = redis
        self.token_budget = token_budget
        self._history: list[dict[str, str]] = []

    async def load(self) -> None:
        """Load history from Redis if available."""
        if self._redis is None:
            return
        try:
            key = f"session:{self.session_id}:history"
            data = await self._redis.get(key)
            if data:
                self._history = json.loads(data)
        except Exception as e:
            logger.warning("failed_to_load_session_history_from_redis", error=str(e))

    def build(
        self,
        *,
        rag_context: str = "",
        memory_context: str = "",
        web_context: str = "",
        tool_history: list[dict[str, Any]] | None = None,
        package: AgentContextPackage | None = None,
    ) -> ContextWindow:
        """
        Assemble the ContextWindow for the current turn.
        Truncates history from oldest messages first if exceeding token budget.
        """
        # If package provided, extract formatted parts
        if package is not None and package.formatted_text:
            combined_context = package.formatted_text
        else:
            parts = []
            if rag_context:
                parts.append(rag_context)
            if memory_context:
                parts.append(f"=== [MEMORY] ===\n{memory_context}")
            if web_context:
                parts.append(f"=== [WEB] ===\n{web_context}")
            combined_context = "\n\n".join(parts)

        # Base token consumption
        sys_tokens = len(_TOKENIZER.encode(_SYSTEM_PROMPT))
        ctx_tokens = len(_TOKENIZER.encode(combined_context))
        tool_json = json.dumps(tool_history or [])
        tool_tokens = len(_TOKENIZER.encode(tool_json))

        allocated_history_budget = max(0, self.token_budget - sys_tokens - ctx_tokens - tool_tokens)

        # Truncate history from oldest to newest to fit allocated budget
        fitted_history: list[dict[str, str]] = []
        history_tokens_used = 0

        for msg in reversed(self._history):
            msg_tokens = len(_TOKENIZER.encode(msg.get("content", ""))) + 4
            if history_tokens_used + msg_tokens > allocated_history_budget:
                break
            fitted_history.insert(0, msg)
            history_tokens_used += msg_tokens

        total_used = sys_tokens + ctx_tokens + tool_tokens + history_tokens_used

        return ContextWindow(
            system_prompt=_SYSTEM_PROMPT,
            history=fitted_history,
            rag_context=rag_context or (package.formatted_text if package else ""),
            tool_history=tool_history or [],
            memory_context=memory_context,
            web_context=web_context,
            token_budget=self.token_budget,
            token_used=total_used,
            package=package,
        )

    async def append_user(self, message: str) -> None:
        self._history.append({"role": "user", "content": message})

    async def append_assistant(self, message: str) -> None:
        self._history.append({"role": "assistant", "content": message})

    async def save(self) -> None:
        """Persist current history to Redis with TTL."""
        if self._redis is None:
            return
        try:
            key = f"session:{self.session_id}:history"
            await self._redis.set(key, json.dumps(self._history), ex=86400)
        except Exception as e:
            logger.warning("failed_to_save_session_history_to_redis", error=str(e))
