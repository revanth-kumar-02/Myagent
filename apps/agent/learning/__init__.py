"""
learning — Kora Adaptive Learning & Self-Reflection Subsystem (V12).

Exports core learning classes and types.
"""

from learning.analyzer import ExecutionAnalyzer
from learning.manager import AdaptiveLearningManager
from learning.reflector import ReflectionEngine
from learning.types import (
    ExecutionTrace,
    FeedbackType,
    LearningCategory,
    LearningRecord,
    LearningStatus,
    ReflectionAnalysis,
    ReflectionReport,
    StepOutcome,
    UserFeedbackRecord,
)
from learning.validator import LearningValidator

__all__ = [
    "LearningCategory",
    "LearningStatus",
    "FeedbackType",
    "StepOutcome",
    "ExecutionTrace",
    "LearningRecord",
    "ReflectionAnalysis",
    "ReflectionReport",
    "UserFeedbackRecord",
    "ExecutionAnalyzer",
    "ReflectionEngine",
    "LearningValidator",
    "AdaptiveLearningManager",
]
