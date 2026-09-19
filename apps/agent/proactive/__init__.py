"""
proactive — Kora Proactive Intelligence & Anti-Spam Subsystem (V15)

Exports:
  - ProactiveIntelligenceEngine
  - EventDetector
  - RelevanceEngine
  - ProactiveDecisionEngine
  - NotificationManager
  - ProactiveTaskManager
  - Types, enums, dataclasses, and configs
"""

from proactive.decision import ProactiveDecisionEngine
from proactive.detector import EventDetector
from proactive.engine import ProactiveIntelligenceEngine
from proactive.notifications import NotificationManager, sanitize_text
from proactive.relevance import RelevanceEngine, map_source_to_category
from proactive.tasks import ProactiveTaskManager, RecursionLimitExceededError
from proactive.types import (
    EventSourceType,
    EventUrgency,
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    ProactiveAction,
    ProactiveConfig,
    ProactiveDecision,
    ProactiveEvent,
    ProactiveNotification,
    RelevanceScore,
    UserFeedback,
)

__all__ = [
    "ProactiveIntelligenceEngine",
    "EventDetector",
    "RelevanceEngine",
    "ProactiveDecisionEngine",
    "NotificationManager",
    "ProactiveTaskManager",
    "RecursionLimitExceededError",
    "sanitize_text",
    "map_source_to_category",
    "EventSourceType",
    "EventUrgency",
    "NotificationCategory",
    "NotificationPriority",
    "NotificationStatus",
    "ProactiveAction",
    "ProactiveConfig",
    "ProactiveDecision",
    "ProactiveEvent",
    "ProactiveNotification",
    "RelevanceScore",
    "UserFeedback",
]
