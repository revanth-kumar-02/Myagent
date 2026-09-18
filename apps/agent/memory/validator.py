"""
memory.validator — Validation and sanitization for candidate memories (RAG V5)

Rules enforced:
  - Reject secrets, passwords, API keys, private keys, bearer tokens
  - Reject complete source-code dumps or full document uploads (must be in RAG, not Memory)
  - Reject empty or low-signal text
  - Compute SHA-256 content hash
  - Bound confidence and importance within [0.0, 1.0]
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import structlog

from memory.types import MemoryRecord, MemorySource, MemoryType
from rag.embedder import is_sensitive_content

logger = structlog.get_logger(__name__)

# Minimum and maximum content bounds for concise long-term memories
MIN_MEMORY_CHARS = 5
MAX_MEMORY_CHARS = 4000
MAX_CODE_LINES = 40

# Heuristics for detecting raw source code files / dumps that belong in RAG
_CODE_DUMP_PATTERNS = [
    re.compile(r"^\s*(?:import\s+[a-zA-Z0-9_\.]+|from\s+[a-zA-Z0-9_\.]+\s+import)", re.MULTILINE),
    re.compile(r"^\s*(?:class\s+[a-zA-Z0-9_]+(?:\(.*\))?:|def\s+[a-zA-Z0-9_]+\(.*\):)", re.MULTILINE),
    re.compile(r"^\s*(?:public\s+class|interface\s+[a-zA-Z0-9_]+|function\s+[a-zA-Z0-9_]+)", re.MULTILINE),
]


class MemoryValidationError(ValueError):
    """Raised when a candidate memory fails validation rules."""


def compute_content_hash(content: str) -> str:
    """Compute normalized SHA-256 hash for content-based deduplication."""
    normalized = " ".join(content.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_candidate_memory(
    content: str,
    memory_type: MemoryType | str,
    confidence: float = 1.0,
    importance: float = 0.5,
    source: MemorySource | str = MemorySource.USER_EXPLICIT,
) -> tuple[str, float, float, str]:
    """
    Validates candidate memory content and parameters.

    Returns:
        (sanitized_content, validated_confidence, validated_importance, content_hash)

    Raises:
        MemoryValidationError: If content contains secrets, code dumps, or invalid bounds.
    """
    clean_content = content.strip()

    # 1. Length validation
    if len(clean_content) < MIN_MEMORY_CHARS:
        raise MemoryValidationError(
            f"Memory content too short ({len(clean_content)} chars). Minimum is {MIN_MEMORY_CHARS} chars."
        )
    if len(clean_content) > MAX_MEMORY_CHARS:
        raise MemoryValidationError(
            f"Memory content too long ({len(clean_content)} chars). Maximum is {MAX_MEMORY_CHARS} chars."
        )

    # 2. Secret & credential detection
    if is_sensitive_content(clean_content):
        logger.warning("memory_validation_rejected_secret_content")
        raise MemoryValidationError("Memory content contains sensitive credentials, private keys, or API tokens.")

    # 3. Code dump / document duplicate detection
    lines = clean_content.splitlines()
    if len(lines) > MAX_CODE_LINES:
        code_matches = sum(1 for p in _CODE_DUMP_PATTERNS if p.search(clean_content))
        if code_matches >= 2:
            raise MemoryValidationError(
                "Memory content resembles a raw source code dump. Code and documents must be indexed in RAG, not Memory."
            )

    # 4. Confidence and importance clamping
    val_confidence = max(0.0, min(1.0, float(confidence)))
    val_importance = max(0.0, min(1.0, float(importance)))

    # 5. Content Hash
    content_hash = compute_content_hash(clean_content)

    return clean_content, val_confidence, val_importance, content_hash
