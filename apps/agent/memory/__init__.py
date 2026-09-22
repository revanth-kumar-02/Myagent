"""
memory — Kora Long-Term Memory Layer (RAG V5)
"""

from memory.conflict import MemoryConflictResolver, cosine_similarity
from memory.decay import calculate_recency_score, compute_memory_score, is_memory_expired
from memory.manager import MemoryManager
from memory.extractor import MemoryCandidate, MemoryCandidateDetector
from memory.types import (
    MemoryRecord,
    MemoryRetrievalResult,
    MemorySource,
    MemoryStats,
    MemoryStatus,
    MemoryType,
)
from memory.validator import (
    MemoryValidationError,
    compute_content_hash,
    validate_candidate_memory,
)

__all__ = [
    "MemoryType",
    "MemoryStatus",
    "MemorySource",
    "MemoryRecord",
    "MemoryRetrievalResult",
    "MemoryStats",
    "MemoryManager",
    "MemoryCandidate",
    "MemoryCandidateDetector",
    "MemoryValidationError",
    "validate_candidate_memory",
    "compute_content_hash",
    "MemoryConflictResolver",
    "cosine_similarity",
    "calculate_recency_score",
    "compute_memory_score",
    "is_memory_expired",
]
