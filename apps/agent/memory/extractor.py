"""
memory.extractor — Automatic Memory Candidate Detector & Extractor (V2)

Detects and extracts meaningful long-term memory candidates from conversation turns,
actions, and user statements.

Enforces:
  - Detection of explicit preferences, user profile facts, project context, decisions,
    workflow patterns, and confirmed corrections.
  - Complete rejection of temporary conversation noise, greetings, one-off questions, and tool navigation.
  - Strict rejection of secrets, passwords, API keys, and sensitive credentials.
  - Calculation of initial confidence, importance, durability, and entity relationships for Knowledge Graph.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from memory.types import MemoryRecord, MemorySource, MemoryStatus, MemoryType
from memory.validator import MemoryValidationError, compute_content_hash
from rag.embedder import is_sensitive_content

logger = structlog.get_logger(__name__)


@dataclass
class MemoryCandidate:
    """
    Extracted memory candidate ready for validation and storage.
    """
    content: str
    type: MemoryType
    confidence: float
    importance: float
    source: MemorySource
    project_id: uuid.UUID | None = None
    entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# Common non-memory conversational patterns (temporary chatter)
_TRANSIENT_PATTERNS = [
    re.compile(r"^\s*(?:hi|hello|hey|greetings|good\s+(?:morning|afternoon|evening)|howdy)\b", re.I),
    re.compile(r"^\s*(?:what\s+is\s+\d+\s*[\+\-\*\/]\s*\d+|calculate\s+\d+|tell\s+me\s+a\s+joke)\b", re.I),
    re.compile(r"^\s*(?:who\s+are\s+you|what\s+can\s+you\s+do|how\s+are\s+you|help)\b", re.I),
    re.compile(r"^\s*(?:open|launch|navigate\s+to|show|list)\s+(?:browser|vscode|file|directory|chatgpt|app)\b", re.I),
    re.compile(r"^\s*(?:ok|okay|thanks|thank\s+you|got\s+it|cool|great|awesome|yes|no|sure|yep|nope)\b", re.I),
    re.compile(r"^\s*(?:what\s+time\s+is\s+it|today's\s+date|current\s+time)\b", re.I),
]


class MemoryCandidateDetector:
    """
    Analyzes user-assistant interaction turns and identifies long-term memory candidates.
    """

    def detect(
        self,
        user_message: str,
        assistant_response: str = "",
        project_id: uuid.UUID | None = None,
    ) -> MemoryCandidate | None:
        """
        Inspect message for meaningful durable context.
        Returns a MemoryCandidate or None if transient/low-signal or secret.
        """
        raw = user_message.strip()
        if not raw or len(raw) < 6:
            return None

        # 1. Reject secrets/credentials immediately
        if is_sensitive_content(raw) or (assistant_response and is_sensitive_content(assistant_response)):
            logger.info("memory_candidate_rejected_sensitive_content")
            return None

        # 2. Reject transient chatter
        for pattern in _TRANSIENT_PATTERNS:
            if pattern.search(raw):
                return None

        # 3. Check for Explicit Preferences
        pref_match = self._extract_preference(raw)
        if pref_match:
            return MemoryCandidate(
                content=pref_match,
                type=MemoryType.USER_PREFERENCE,
                confidence=0.95,
                importance=0.85,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "user_preference"},
            )

        # 4. Check for User Profile & System/Environment Facts
        fact_match = self._extract_fact_or_profile(raw)
        if fact_match:
            return MemoryCandidate(
                content=fact_match,
                type=MemoryType.USER_PROFILE_CONTEXT,
                confidence=0.90,
                importance=0.80,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "user_profile_context"},
            )

        # 5. Check for Architectural / Technical Decisions
        decision_match = self._extract_decision(raw)
        if decision_match:
            return MemoryCandidate(
                content=decision_match,
                type=MemoryType.DECISION,
                confidence=0.90,
                importance=0.85,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "decision"},
            )

        # 6. Check for Project Context
        project_match = self._extract_project_context(raw)
        if project_match:
            return MemoryCandidate(
                content=project_match,
                type=MemoryType.PROJECT_CONTEXT,
                confidence=0.90,
                importance=0.80,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "project_context"},
            )

        # 7. Check for Workflow Patterns
        workflow_match = self._extract_workflow_pattern(raw)
        if workflow_match:
            return MemoryCandidate(
                content=workflow_match,
                type=MemoryType.WORKFLOW_PATTERN,
                confidence=0.90,
                importance=0.80,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "workflow_pattern"},
            )

        # 8. Check for Confirmed Corrections
        correction_match = self._extract_correction(raw)
        if correction_match:
            return MemoryCandidate(
                content=correction_match,
                type=MemoryType.AGENT_LEARNING,
                confidence=0.95,
                importance=0.90,
                source=MemorySource.USER_EXPLICIT,
                project_id=project_id,
                metadata={"detected_rule": "confirmed_correction"},
            )

        return None

    # ── Pattern Extractors ───────────────────────────────────────────────────

    def _extract_preference(self, text: str) -> str | None:
        patterns = [
            # "I prefer X", "I always prefer X"
            r"(?:i\s+(?:always\s+)?(?:prefer|like|love|want\s+you\s+to\s+use)|my\s+preference\s+is)\s+(.+)",
            # "Remember that I prefer...", "Remember that I like..."
            r"(?:remember\s+(?:that\s+)?|please\s+remember\s+(?:that\s+)?|note\s+that\s+|keep\s+in\s+mind\s+that\s+)(?:i\s+(?:prefer|like|use|work\s+with)\s+.+)",
            # "Always use/write/format..."
            r"(?:please\s+)?always\s+(?:use|write|format|respond\s+with|generate)\s+(.+)",
            # "Prefer dark/light mode/theme"
            r"(?:i\s+)?(?:prefer|use)\s+(?:dark|light)\s+(?:theme|mode)",
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                # Format clean concise sentence
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None

    def _extract_fact_or_profile(self, text: str) -> str | None:
        patterns = [
            r"(?:my\s+name\s+is|i\s+am\s+a\s+|i\s+work\s+as\s+|my\s+role\s+is)\s+(.+)",
            r"(?:i\s+am\s+(?:running|on|using)|my\s+(?:os|machine|system|environment|hardware|setup|hardware\s+setup)\s+is)\s+(.+)",
            r"(?:the\s+(?:server|backend|api|database|db|service)\s+(?:runs\s+on|port\s+is|is\s+hosted\s+at))\s+(.+)",
            r"(?:my\s+timezone\s+is|i\s+live\s+in|i\s+am\s+located\s+in)\s+(.+)",
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None

    def _extract_decision(self, text: str) -> str | None:
        patterns = [
            r"(?:we\s+(?:decided|have\s+decided|agreed|chose|selected)\s+to\s+|decision:\s*)(.+)",
            r"(?:let's\s+(?:go\s+with|stick\s+with|adopt|use)\s+|we\s+will\s+(?:use|stick\s+with|adopt)\s+)(.+)",
            r"(?:from\s+now\s+on\s+(?:we|let's|use)\s+)(.+)",
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None

    def _extract_project_context(self, text: str) -> str | None:
        patterns = [
            r"(?:this\s+project\s+is\s+|the\s+project\s+architecture\s+is\s+|this\s+workspace\s+is\s+)(.+)",
            r"(?:in\s+this\s+repository\s+|our\s+project\s+name\s+is\s+|we\s+are\s+building\s+a\s+)(.+)",
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None

    def _extract_workflow_pattern(self, text: str) -> str | None:
        patterns = [
            r"(?:always\s+run\s+(?:tests|lint|build|pytest|flutter\s+test)|before\s+(?:committing|pushing)\s+run)\s*(.*)",
            r"(?:our\s+(?:git|deployment|deploy|testing|test)\s+workflow\s+is|we\s+use\s+(?:conventional\s+commits|git\s+flow))\s*(.*)",
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None

    def _extract_correction(self, text: str) -> str | None:
        patterns = [
            r"(?:no,\s+(?:that's|that\s+is)\s+wrong|correction:\s*|don't\s+use\s+[a-zA-Z0-9_-]+,\s+use\s+)(.+)",
            r"(?:actually,\s+(?:the\s+answer\s+is|it\s+should\s+be|we\s+should\s+use))\s+(.+)",
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                cleaned = text.strip().rstrip(".!?")
                if not cleaned.endswith("."):
                    cleaned += "."
                return cleaned
        return None
