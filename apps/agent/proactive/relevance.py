"""
proactive.relevance — Relevance Engine & Anti-Spam (V15)

Evaluates whether a detected event warrants user attention by assessing:
  - Multi-factor score (urgency, importance, project context, recent user activity)
  - Anti-spam rules: exact deduplication, per-category cooldowns, exponential backoff
  - Hourly notification rate limits & quiet hours
  - User category preferences & priority thresholds
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import structlog

from proactive.types import (
    EventSourceType,
    EventUrgency,
    NotificationCategory,
    NotificationPriority,
    ProactiveConfig,
    ProactiveEvent,
    RelevanceScore,
)

logger = structlog.get_logger(__name__)


def map_source_to_category(source: EventSourceType) -> NotificationCategory:
    """Map an event source type to its primary notification category."""
    mapping = {
        EventSourceType.SCHEDULED_TASK: NotificationCategory.TASK,
        EventSourceType.TASK_LIFECYCLE: NotificationCategory.TASK,
        EventSourceType.PROJECT_FILE_CHANGE: NotificationCategory.PROJECT,
        EventSourceType.AUTOMATION: NotificationCategory.AUTOMATION,
        EventSourceType.SYSTEM_EVENT: NotificationCategory.SYSTEM,
        EventSourceType.MEMORY_CHANGE: NotificationCategory.MEMORY,
        EventSourceType.EXTERNAL_CHECK: NotificationCategory.SYSTEM,
    }
    return mapping.get(source, NotificationCategory.SYSTEM)


class RelevanceEngine:
    """
    Evaluates relevance, urgency, anti-spam constraints, and user preferences for events.
    """

    def __init__(self, config: ProactiveConfig | None = None) -> None:
        self.config = config or ProactiveConfig()

        # Anti-spam caches (in-memory tracking)
        # content_hash -> timestamp of last notification
        self._hash_history: dict[str, float] = {}
        # content_hash -> repeat count
        self._hash_repeat_count: dict[str, int] = defaultdict(int)
        # category -> timestamp of last notification
        self._category_last_sent: dict[NotificationCategory, float] = {}
        # sliding window of notification timestamps for rate limiting
        self._hourly_history: deque[float] = deque()

    def evaluate(
        self,
        event: ProactiveEvent,
        active_project_id: uuid.UUID | None = None,
        recent_activity: bool = False,
    ) -> RelevanceScore:
        """
        Evaluate an event against relevance metrics and anti-spam constraints.
        """
        reasons: list[str] = []
        now = time.monotonic()
        category = map_source_to_category(event.source_type)

        # 1. Check Global Engine Enablement
        if not self.config.enabled:
            return RelevanceScore(
                score=0.0,
                urgency=event.urgency,
                importance=event.importance,
                should_notify=False,
                reasons=["Proactive intelligence globally disabled in config"],
            )

        # 2. Check Category Enablement
        if category not in self.config.enabled_categories:
            return RelevanceScore(
                score=0.0,
                urgency=event.urgency,
                importance=event.importance,
                should_notify=False,
                reasons=[f"Category '{category.value}' is disabled in user preferences"],
            )

        # 3. Base Scoring Calculation
        # Weights: importance (40%), urgency (35%), project context (15%), recent activity (10%)
        importance_weight = max(0.0, min(1.0, event.importance))

        urgency_multipliers = {
            EventUrgency.CRITICAL: 1.0,
            EventUrgency.HIGH: 0.8,
            EventUrgency.NORMAL: 0.5,
            EventUrgency.LOW: 0.2,
        }
        urgency_weight = urgency_multipliers.get(event.urgency, 0.5)

        project_weight = 0.5
        if event.project_id is not None:
            if active_project_id is not None and event.project_id == active_project_id:
                project_weight = 1.0
                reasons.append("Matches currently active project context")
            else:
                project_weight = 0.3
                reasons.append("Event is for non-active project")
        else:
            project_weight = 0.5

        activity_weight = 1.0 if recent_activity else 0.4
        if recent_activity:
            reasons.append("Recent user activity observed on related scope")

        raw_score = (
            (importance_weight * 0.40)
            + (urgency_weight * 0.35)
            + (project_weight * 0.15)
            + (activity_weight * 0.10)
        )
        final_score = round(max(0.0, min(1.0, raw_score)), 3)
        reasons.append(f"Composite relevance score: {final_score:.2f} (Threshold: {self.config.min_relevance_score})")

        # 4. Anti-Spam: Deduplication & Cooldown Check
        is_urgent = event.urgency in (EventUrgency.CRITICAL, EventUrgency.HIGH)

        # A. Exact Hash Deduplication & Exponential Backoff
        repeat_count = self._hash_repeat_count[event.content_hash]
        last_hash_time = self._hash_history.get(event.content_hash)

        base_cooldown = self.config.category_cooldowns.get(category, 300)
        backoff_cooldown = base_cooldown * min(8, (2 ** repeat_count))

        if last_hash_time and (now - last_hash_time < backoff_cooldown):
            # Same event within backoff window
            reasons.append(f"Suppressed duplicate event (repeated {repeat_count} times, backoff {backoff_cooldown}s)")
            return RelevanceScore(
                score=final_score,
                urgency=event.urgency,
                importance=event.importance,
                should_notify=False,
                reasons=reasons,
                deduplicated=True,
            )

        # B. Category Cooldown (unless event is urgent/critical)
        last_cat_time = self._category_last_sent.get(category)
        if not is_urgent and last_cat_time and (now - last_cat_time < base_cooldown):
            reasons.append(f"Category '{category.value}' cooldown active ({int(base_cooldown - (now - last_cat_time))}s remaining)")
            return RelevanceScore(
                score=final_score,
                urgency=event.urgency,
                importance=event.importance,
                should_notify=False,
                reasons=reasons,
                cooldown_active=True,
            )

        # C. Hourly Rate Limiting
        # Purge items older than 3600 seconds
        while self._hourly_history and (now - self._hourly_history[0] > 3600):
            self._hourly_history.popleft()

        if not is_urgent and len(self._hourly_history) >= self.config.max_notifications_per_hour:
            reasons.append(f"Hourly notification limit reached ({len(self._hourly_history)}/{self.config.max_notifications_per_hour})")
            return RelevanceScore(
                score=final_score,
                urgency=event.urgency,
                importance=event.importance,
                should_notify=False,
                reasons=reasons,
            )

        # D. Quiet Hours Check
        if self.config.quiet_hours_enabled and not is_urgent:
            current_hour = datetime.now(timezone.utc).hour
            if self._in_quiet_hours(current_hour):
                reasons.append(f"Suppressed during quiet hours ({self.config.quiet_hours_start}:00 - {self.config.quiet_hours_end}:00 UTC)")
                return RelevanceScore(
                    score=final_score,
                    urgency=event.urgency,
                    importance=event.importance,
                    should_notify=False,
                    reasons=reasons,
                )

        # 5. Score Threshold Check
        should_notify = final_score >= self.config.min_relevance_score
        if not should_notify:
            reasons.append(f"Score {final_score:.2f} is below minimum threshold {self.config.min_relevance_score}")

        return RelevanceScore(
            score=final_score,
            urgency=event.urgency,
            importance=event.importance,
            should_notify=should_notify,
            reasons=reasons,
        )

    def record_notification_delivered(self, event: ProactiveEvent) -> None:
        """Update anti-spam caches when a notification is successfully created or delivered."""
        now = time.monotonic()
        category = map_source_to_category(event.source_type)

        self._hash_history[event.content_hash] = now
        self._hash_repeat_count[event.content_hash] += 1
        self._category_last_sent[category] = now
        self._hourly_history.append(now)

    def reset_cooldowns(self) -> None:
        """Clear all cooldown and anti-spam histories (useful for testing)."""
        self._hash_history.clear()
        self._hash_repeat_count.clear()
        self._category_last_sent.clear()
        self._hourly_history.clear()

    def _in_quiet_hours(self, current_hour: int) -> bool:
        """Determine if a given UTC hour falls within the configured quiet hours."""
        start = self.config.quiet_hours_start
        end = self.config.quiet_hours_end
        if start <= end:
            return start <= current_hour < end
        else:
            # Over midnight wrap (e.g. 22:00 to 07:00)
            return current_hour >= start or current_hour < end
