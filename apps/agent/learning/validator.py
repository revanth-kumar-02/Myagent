"""
learning.validator — Learning Validation, Secret Protection & Contradiction Resolution (V12).

Responsibilities:
  - Secret & sensitive credential sanitization
  - Duplicate detection and content hashing
  - Grounding verification against source evidence
  - Contradiction resolution and superseding
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Sequence

import structlog

from learning.types import LearningCategory, LearningRecord, LearningStatus

logger = structlog.get_logger(__name__)

# Secret detection regexes
_SECRET_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey|secret|token|password|passwd|auth_token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(?:bearer\s+[A-Za-z0-9_\-\.]{16,})", re.IGNORECASE),
    re.compile(r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,})", re.IGNORECASE),
    re.compile(r"(?:sk-[A-Za-z0-9]{32,}|sk-ant-[A-Za-z0-9_\-]{32,})", re.IGNORECASE),
    re.compile(r"(?:-----BEGIN\s+(?:RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY-----)", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """Mask secrets and credentials with [REDACTED_SECRET]."""
    sanitized = text
    for pat in _SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def compute_learning_hash(category: LearningCategory, condition: str, recommendation: str) -> str:
    """Compute deterministic SHA-256 hash for duplicate detection."""
    norm_cat = category.value.strip().lower()
    norm_cond = condition.strip().lower()
    norm_rec = recommendation.strip().lower()
    payload = f"{norm_cat}|{norm_cond}|{norm_rec}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LearningValidator:
    """
    Validates candidate learnings for safety, evidence grounding, and uniqueness.
    """

    def validate_candidate(
        self,
        candidate: LearningRecord,
        existing_learnings: Sequence[LearningRecord] | None = None,
    ) -> tuple[bool, str, LearningRecord]:
        """
        Validate, sanitize, and verify grounding for a candidate LearningRecord.
        Returns: (is_valid, reason, sanitized_record)
        """
        # 1. Minimum confidence threshold
        if candidate.confidence < 0.4:
            return False, f"Confidence {candidate.confidence:.2f} is below minimum threshold (0.4)", candidate

        # 2. Secret & Sensitive Data Sanitization
        candidate.title = sanitize_text(candidate.title)
        candidate.description = sanitize_text(candidate.description)
        candidate.condition = sanitize_text(candidate.condition)
        candidate.recommendation = sanitize_text(candidate.recommendation)

        # Check if entire recommendation was a raw secret
        if "[REDACTED_SECRET]" in candidate.recommendation and len(candidate.recommendation.replace("[REDACTED_SECRET]", "").strip()) < 5:
            return False, "Learning contains only sensitive credential content", candidate

        # 3. Content Hashing & Duplicate Detection
        candidate.content_hash = compute_learning_hash(
            candidate.category, candidate.condition, candidate.recommendation
        )

        existing_list = existing_learnings or []
        for existing in existing_list:
            if existing.status == LearningStatus.ACTIVE and existing.content_hash == candidate.content_hash:
                # Same project scope or global
                if existing.project_id == candidate.project_id:
                    logger.info("duplicate_learning_rejected", learning_id=str(existing.learning_id))
                    return False, f"Duplicate of existing active learning '{existing.learning_id}'", existing

        # 4. Evidence Grounding Verification
        if not candidate.evidence and candidate.source_task_id is None:
            return False, "Learning lacks supporting execution evidence or source task ID", candidate

        # 5. Contradiction Handling & Superseding
        for existing in existing_list:
            if existing.status == LearningStatus.ACTIVE and existing.project_id == candidate.project_id:
                if self._is_contradiction(candidate, existing):
                    logger.info(
                        "contradictory_learning_superseding",
                        new_id=str(candidate.learning_id),
                        superseded_id=str(existing.learning_id),
                    )
                    existing.status = LearningStatus.DEPRECATED
                    candidate.importance = max(candidate.importance, existing.importance + 0.1)

        # Clamp confidence and importance
        candidate.confidence = min(max(candidate.confidence, 0.0), 1.0)
        candidate.importance = min(max(candidate.importance, 0.0), 1.0)

        return True, "validated", candidate

    def _is_contradiction(self, new_rec: LearningRecord, old_rec: LearningRecord) -> bool:
        """Check if new learning contradicts an older one."""
        if new_rec.category != old_rec.category:
            return False

        new_rec_norm = new_rec.recommendation.lower()
        old_rec_norm = old_rec.recommendation.lower()

        # Check for opposing directives (e.g. "use X" vs "avoid X" or "X failed")
        if "avoid" in new_rec_norm and "use" in old_rec_norm:
            # Check if they target the same tool/target
            for word in old_rec_norm.split():
                if len(word) > 4 and word in new_rec_norm:
                    return True
        return False
