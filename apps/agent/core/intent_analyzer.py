"""
core.intent_analyzer — Intent Analyzer & Context Decision Engine (V7)

Responsibilities:
  - Classify incoming user requests into fine-grained IntentTypes:
      - GENERAL_CONVERSATION
      - KNOWLEDGE_RAG
      - MEMORY
      - WEB_RESEARCH
      - TOOL_ACTION
      - MULTI_STEP_TASK
      - MIXED_REQUEST
  - Derive precise ContextNeed to prevent wasteful retrieval
"""

from __future__ import annotations

import re
import uuid

import structlog

from core.context_resolver import ContextResolver
from core.types import ContextNeed, IntentType, SourceType

logger = structlog.get_logger(__name__)

# Patterns indicating direct tool / terminal / file manipulation actions
_TOOL_PATTERNS = [
    re.compile(r"\b(?:run pytest|run tests?|execute command|run bash|git commit|git push|create\s+(?:a\s+|an\s+|new\s+)?file|write\s+(?:a\s+|to\s+)?file|edit\s+(?:a\s+)?file|delete\s+(?:a\s+)?file|modify\s+(?:a\s+)?file|mkdir|open\s+(?:vs\s*code|vscode|code|browser|terminal|app|application)|launch\s+(?:vs\s*code|vscode|code|app|application))\b", re.IGNORECASE),
    re.compile(r"\b(?:apply migration|run build|npm run|cargo test|flutter run|execute script)\b", re.IGNORECASE),
    re.compile(r"\b(?:system\s+(?:info|information)|show\s+(?:my\s+)?system|check\s+(?:my\s+)?system|what\s+is\s+my\s+os|what\s+os|system\s+hardware|cpu\s+info|os\s+version|hardware\s+info)\b", re.IGNORECASE),
    re.compile(r"\b(?:read\s+clipboard|check\s+clipboard|what(?:'s|\s+is)\s+(?:in\s+)?(?:my\s+)?clipboard|paste\s+clipboard|copy\s+to\s+clipboard|write\s+(?:to\s+)?clipboard)\b", re.IGNORECASE),
    re.compile(r"\b(?:what\s+processes\s+are\s+running|list\s+processes|running\s+processes|check\s+processes|show\s+processes)\b", re.IGNORECASE),
    re.compile(r"\b(?:find\s+(?:this\s+)?file|search\s+for\s+file|list\s+files\s+in|show\s+files\s+in)\b", re.IGNORECASE),
]

# Patterns indicating multi-step sequential tasks
_MULTI_STEP_PATTERNS = [
    re.compile(r"\b(?:first\s+.*,\s*(?:then|next|after that)|step 1|and then|then also|followed by)\b", re.IGNORECASE),
    re.compile(r"\b(?:refactor.*and test|search.*and create|investigate.*and fix)\b", re.IGNORECASE),
]


class IntentAnalyzer:
    """
    Analyzes user messages to determine IntentType and exact ContextNeed.
    """

    def __init__(self, context_resolver: ContextResolver | None = None) -> None:
        self._resolver = context_resolver or ContextResolver()

    def analyze(
        self,
        message: str,
        project_id: uuid.UUID | None = None,
        has_active_project: bool = True,
    ) -> tuple[IntentType, ContextNeed]:
        """
        Classifies request intent and determines context retrieval necessity.
        """
        msg_clean = message.strip()
        if not msg_clean:
            return IntentType.GENERAL_CONVERSATION, ContextNeed.NONE

        # 0. Check explicit slash commands
        if re.match(r"^/(?:search|research|web)\b", msg_clean, re.IGNORECASE):
            return IntentType.WEB_RESEARCH, ContextNeed.WEB
        if re.match(r"^/(?:rag|codebase|knowledge)\b", msg_clean, re.IGNORECASE):
            return IntentType.KNOWLEDGE_RAG, ContextNeed.RAG
        if re.match(r"^/(?:memory|remember|profile)\b", msg_clean, re.IGNORECASE):
            return IntentType.MEMORY, ContextNeed.MEMORY
        if re.match(r"^/[a-zA-Z0-9_-]+", msg_clean):
            return IntentType.TOOL_ACTION, ContextNeed.NONE

        # 1. Resolve context sources needed
        resolved_sources = self._resolver.resolve(
            message=msg_clean,
            project_id=project_id,
            has_active_project=has_active_project,
        )

        # 2. Check for Multi-step task
        is_multi_step = any(p.search(msg_clean) for p in _MULTI_STEP_PATTERNS)
        # 3. Check for Tool action
        is_tool = any(p.search(msg_clean) for p in _TOOL_PATTERNS)

        # 4. Determine ContextNeed
        context_need = self._derive_context_need(resolved_sources)

        # 5. Determine IntentType
        if is_multi_step:
            intent = IntentType.MULTI_STEP_TASK
        elif is_tool:
            intent = IntentType.TOOL_ACTION
        elif len(resolved_sources) > 1:
            intent = IntentType.MIXED_REQUEST
        elif SourceType.RAG in resolved_sources:
            intent = IntentType.KNOWLEDGE_RAG
        elif SourceType.MEMORY in resolved_sources:
            intent = IntentType.MEMORY
        elif SourceType.WEB in resolved_sources:
            intent = IntentType.WEB_RESEARCH
        else:
            intent = IntentType.GENERAL_CONVERSATION

        logger.debug(
            "intent_analyzed",
            message=msg_clean[:40],
            intent=intent.value,
            context_need=context_need.value,
        )
        return intent, context_need

    def _derive_context_need(self, sources: set[SourceType]) -> ContextNeed:
        """Map resolved SourceType set to explicit ContextNeed."""
        has_rag = SourceType.RAG in sources
        has_mem = SourceType.MEMORY in sources
        has_web = SourceType.WEB in sources

        if has_rag and has_mem and has_web:
            return ContextNeed.ALL
        if has_rag and has_mem:
            return ContextNeed.RAG_AND_MEMORY
        if has_rag and has_web:
            return ContextNeed.RAG_AND_WEB
        if has_mem and has_web:
            return ContextNeed.MEMORY_AND_WEB
        if has_rag:
            return ContextNeed.RAG
        if has_mem:
            return ContextNeed.MEMORY
        if has_web:
            return ContextNeed.WEB
        return ContextNeed.NONE
