"""
core.context_resolver — Context Need Resolver & Retrieval Router (RAG V4)

Responsibilities:
  - Classify incoming user requests to determine which context sources are needed:
      - Project RAG (local codebase, indexed documents, files, sheets, slides)
      - Long-Term Memory (user preferences, remembered facts, personal history)
      - Web Research (real-time data, external docs, current news, web searches)
      - Mixed combinations
      - None / Direct (conversational greetings, simple logic, basic math)
  - Prevent wasteful or irrelevant retrieval operations
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog

from core.types import SourceType

logger = structlog.get_logger(__name__)

# Patterns indicating project / local codebase queries
_PROJECT_PATTERNS = [
    re.compile(r"\b(?:code|function|class|method|file|module|package|schema|database|table|query|repo|project|endpoint|component|struct|interface)\b", re.IGNORECASE),
    re.compile(r"\b(?:sheet|slide|page|heading|section|pdf|docx|xlsx|pptx|csv|json|yaml|sql|dart|python|typescript)\b", re.IGNORECASE),
    re.compile(r"\b(?:where is|how does|show me|find in|look in|architecture of|in this project|in our codebase|implementation of)\b", re.IGNORECASE),
    re.compile(r"\.(?:py|ts|tsx|js|dart|java|kt|sql|md|pdf|docx|xlsx|pptx|csv|json)\b", re.IGNORECASE),
]

# Patterns indicating personal preference / memory queries (RAG V5 Memory System)
_MEMORY_PATTERNS = [
    re.compile(r"\b(?:my preference|my favorite|i prefer|i like|remember that|remember when|did i mention|my name is|my settings|as i said|previously told)\b", re.IGNORECASE),
    re.compile(r"\b(?:what is my|do you remember|my style|my workflow|my role|my background|my setup|my timezone|my hardware|who am i|about me)\b", re.IGNORECASE),
    re.compile(r"\b(?:project convention|our convention|custom rule|our standard|what did we agree|past decision|we decided|decision on|learning from)\b", re.IGNORECASE),
    re.compile(r"\b(?:workflow pattern|preferred workflow|deploy pattern|how do i usually|how do we usually|last time we fixed|lesson learned)\b", re.IGNORECASE),
]

# Patterns indicating external / real-time / web research queries
_WEB_PATTERNS = [
    re.compile(r"\b(?:search the web|search online|look up on google|browse web|latest news|current price|weather in|who is the current)\b", re.IGNORECASE),
    re.compile(r"\b(?:today|this week|release notes 2026|new in 2026|stock price|real-time|external docs|official documentation for)\b", re.IGNORECASE),
    re.compile(r"\b(?:latest|online|web search|best practices online|current best practices)\b", re.IGNORECASE),
    re.compile(r"https?://[^\s]+", re.IGNORECASE),
]

# Patterns indicating graph relationship / architecture / dependency queries (V11)
_GRAPH_PATTERNS = [
    re.compile(r"\b(?:depends on|dependency|dependencies|architecture|relationship|relationships|connected to|related entities|who uses|what uses|implements|subgraph|call graph|class hierarchy|data flow)\b", re.IGNORECASE),
]

# Patterns indicating simple conversational or math queries that need zero retrieval
_CONVERSATIONAL_PATTERNS = [
    re.compile(r"^(?:hi|hello|hey|greetings|howdy|good morning|good afternoon|good evening|bye|goodbye|see you|thanks|thank you|thanks a lot|thx|cheers|cool|ok|okay|nice)\b.*$", re.IGNORECASE),
    re.compile(r"^(?:what is\s+\d+\s*[\+\-\*\/]\s*\d+|calculate\s+\d+|tell me a joke|flip a coin|roll a die)[!.?]*$", re.IGNORECASE),
]


class ContextResolver:
    """
    Analyzes user messages to determine necessary context sources.
    """

    def resolve(
        self,
        message: str,
        project_id: uuid.UUID | None = None,
        has_active_project: bool = True,
    ) -> set[SourceType]:
        """
        Determine which context sources should be queried for the given message.
        """
        msg_clean = message.strip()
        if not msg_clean:
            return set()

        # 1. Check for pure conversational / trivial direct questions
        for pattern in _CONVERSATIONAL_PATTERNS:
            if pattern.match(msg_clean):
                logger.debug("context_resolver_resolved_none", reason="conversational_pattern")
                return set()

        sources: set[SourceType] = set()

        # 2. Check Memory patterns
        if any(p.search(msg_clean) for p in _MEMORY_PATTERNS):
            sources.add(SourceType.MEMORY)

        # 3. Check Web Research patterns
        if any(p.search(msg_clean) for p in _WEB_PATTERNS):
            sources.add(SourceType.WEB)

        # 4. Check Project RAG patterns
        if (project_id is not None or has_active_project) and any(p.search(msg_clean) for p in _PROJECT_PATTERNS):
            sources.add(SourceType.RAG)

        # 5. Check Knowledge Graph patterns
        if (project_id is not None or has_active_project) and any(p.search(msg_clean) for p in _GRAPH_PATTERNS):
            sources.add(SourceType.GRAPH)
            # Graph queries on codebase also benefit from RAG chunks
            sources.add(SourceType.RAG)

        # 6. Default fallback: if a project is active and no other source was matched,
        # and message is a substantive question (e.g. "how do we authenticate?"), default to RAG
        if not sources and (project_id is not None or has_active_project):
            if len(msg_clean.split()) >= 3 and not msg_clean.endswith("?"):
                sources.add(SourceType.RAG)
            elif "?" in msg_clean and len(msg_clean.split()) >= 3:
                sources.add(SourceType.RAG)

        logger.debug(
            "context_resolver_resolved",
            message=msg_clean[:40],
            sources=[s.value for s in sources],
        )
        return sources

