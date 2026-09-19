"""
proactive.types — Data types, enumerations, and schemas for Kora Proactive Intelligence (V15).

Defines:
  - Event sources and decision classifications (IGNORE, INFORM, SUGGEST, ASK, ACT)
  - Multi-factor relevance models & urgency levels
  - Structured notification payloads with snooze/dismiss/action states
  - User configuration and anti-spam control preferences
"""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ProactiveDecision(str, enum.Enum):
    """Core proactive decision classifications."""
    IGNORE  = "ignore"   # Drop, irrelevant, cooldown or spam
    INFORM  = "inform"   # Informational notification, no action required
    SUGGEST = "suggest"  # Propose recommended action with 1-click execution
    ASK     = "ask"      # Require user confirmation/input before proceeding
    ACT     = "act"      # Execute safe, pre-authorized internal action


class EventSourceType(str, enum.Enum):
    """Source origin of detected proactive events."""
    SCHEDULED_TASK      = "scheduled_task"
    TASK_LIFECYCLE      = "task_lifecycle"
    PROJECT_FILE_CHANGE = "project_file_change"
    AUTOMATION          = "automation"
    SYSTEM_EVENT        = "system_event"
    MEMORY_CHANGE       = "memory_change"
    EXTERNAL_CHECK      = "external_check"


class EventUrgency(str, enum.Enum):
    """Urgency level of detected event."""
    LOW      = "low"
    NORMAL   = "normal"
    HIGH     = "high"
    CRITICAL = "critical"


class NotificationPriority(str, enum.Enum):
    """Priority level for user notification display and routing."""
    LOW    = "low"
    NORMAL = "normal"
    HIGH   = "high"
    URGENT = "urgent"


class NotificationCategory(str, enum.Enum):
    """Category classification for user control and rate-limiting."""
    TASK       = "task"
    PROJECT    = "project"
    SYSTEM     = "system"
    MEMORY     = "memory"
    LEARNING   = "learning"
    SECURITY   = "security"
    AUTOMATION = "automation"


class NotificationStatus(str, enum.Enum):
    """Lifecycle status of a proactive notification."""
    PENDING   = "pending"
    DELIVERED = "delivered"
    DISMISSED = "dismissed"
    SNOOZED   = "snoozed"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    EXECUTED  = "executed"


@dataclass
class ProactiveAction:
    """Pre-packaged or suggested executable action for a notification."""
    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    requires_permission: bool = True
    permission_level: str = "normal"  # 'normal', 'sensitive', 'critical'
    action_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class ProactiveEvent:
    """Normalized proactive event detected across the environment."""
    source_type: EventSourceType
    title: str
    description: str = ""
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    data: dict[str, Any] = field(default_factory=dict)
    urgency: EventUrgency = EventUrgency.NORMAL
    importance: float = 0.5  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.source_type, str):
            self.source_type = EventSourceType(self.source_type)
        if isinstance(self.urgency, str):
            self.urgency = EventUrgency(self.urgency)
        if not self.content_hash:
            self.content_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash for deduplication."""
        raw_key = f"{self.source_type.value}:{self.project_id}:{self.task_id}:{self.title}:{json.dumps(self.data, sort_keys=True)}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


@dataclass
class RelevanceScore:
    """Multi-factor relevance evaluation results."""
    score: float                      # 0.0 to 1.0 composite score
    urgency: EventUrgency
    importance: float                 # 0.0 to 1.0 base importance
    confidence: float = 1.0           # 0.0 to 1.0 evaluation confidence
    should_notify: bool = True
    reasons: list[str] = field(default_factory=list)
    deduplicated: bool = False
    cooldown_active: bool = False


@dataclass
class ProactiveNotification:
    """Structured proactive notification delivered to user / client."""
    title: str
    message: str
    event: ProactiveEvent
    priority: NotificationPriority = NotificationPriority.NORMAL
    decision: ProactiveDecision = ProactiveDecision.INFORM
    category: NotificationCategory = NotificationCategory.SYSTEM
    status: NotificationStatus = NotificationStatus.PENDING
    project_id: uuid.UUID | None = None
    related_task_id: uuid.UUID | None = None
    action: ProactiveAction | None = None
    notification_id: uuid.UUID = field(default_factory=uuid.uuid4)
    snooze_until: datetime | None = None
    delivered_at: datetime | None = None
    responded_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.priority, str):
            self.priority = NotificationPriority(self.priority)
        if isinstance(self.decision, str):
            self.decision = ProactiveDecision(self.decision)
        if isinstance(self.category, str):
            self.category = NotificationCategory(self.category)
        if isinstance(self.status, str):
            self.status = NotificationStatus(self.status)


@dataclass
class ProactiveConfig:
    """User-configurable controls for proactive intelligence and notifications."""
    enabled: bool = True
    min_priority: NotificationPriority = NotificationPriority.LOW
    min_relevance_score: float = 0.55
    enabled_categories: set[NotificationCategory] = field(
        default_factory=lambda: {
            NotificationCategory.TASK,
            NotificationCategory.PROJECT,
            NotificationCategory.SYSTEM,
            NotificationCategory.MEMORY,
            NotificationCategory.LEARNING,
            NotificationCategory.SECURITY,
            NotificationCategory.AUTOMATION,
        }
    )
    category_cooldowns: dict[NotificationCategory, int] = field(
        default_factory=lambda: {
            NotificationCategory.TASK: 120,        # 2 minutes
            NotificationCategory.PROJECT: 300,     # 5 minutes
            NotificationCategory.SYSTEM: 600,      # 10 minutes
            NotificationCategory.MEMORY: 300,      # 5 minutes
            NotificationCategory.LEARNING: 300,    # 5 minutes
            NotificationCategory.SECURITY: 30,     # 30 seconds (high priority)
            NotificationCategory.AUTOMATION: 180,  # 3 minutes
        }
    )
    max_notifications_per_hour: int = 12
    allow_autonomous_actions: bool = False  # If False, ACT will degrade to ASK/SUGGEST
    quiet_hours_enabled: bool = False
    quiet_hours_start: int = 22  # 22:00 (10 PM)
    quiet_hours_end: int = 7     # 07:00 (7 AM)
    max_proactive_depth: int = 2 # Prevent infinite follow-up task cascades


@dataclass
class UserFeedback:
    """User response to a proactive notification."""
    notification_id: uuid.UUID
    action_type: str  # 'dismiss', 'snooze', 'approve', 'reject'
    snooze_minutes: int | None = None
    feedback_text: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
