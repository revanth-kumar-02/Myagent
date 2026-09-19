"""
proactive.notifications — Notification System & User Feedback (V15)

Manages the lifecycle of proactive notifications:
  - Creation, storage, querying, and WebSocket delivery
  - User feedback handling: dismiss, snooze, approve, reject
  - Automatic secret/credential sanitization on all outbound notifications
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

import structlog

from proactive.types import (
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    ProactiveAction,
    ProactiveDecision,
    ProactiveEvent,
    ProactiveNotification,
    UserFeedback,
)

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]

# Secret sanitization patterns (prevent leaking tokens/keys in notifications)
_KEY_VALUE_PATTERN = re.compile(
    r'(?i)(api[_-]?key|secret|token|password|bearer|auth)[\s:=]+["\']?([a-zA-Z0-9_\-\.]{8,})["\']?'
)
_TOKEN_PATTERNS = [
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    re.compile(r'hf_[a-zA-Z0-9]{20,}'),
]


def sanitize_text(text: str) -> str:
    """Mask credentials and sensitive tokens from user-facing text."""
    if not text:
        return text
    sanitized = text
    # Replace key-value pairs
    sanitized = _KEY_VALUE_PATTERN.sub(r'\1: [REDACTED]', sanitized)
    # Replace direct tokens
    for pat in _TOKEN_PATTERNS:
        sanitized = pat.sub('[REDACTED]', sanitized)
    return sanitized


class NotificationManager:
    """
    Coordinates storage, lifecycle, sanitization, and user interactions
    for proactive notifications.
    """

    def __init__(self) -> None:
        self._notifications: dict[uuid.UUID, ProactiveNotification] = {}
        self._feedback_log: list[UserFeedback] = []

    def create_notification(
        self,
        event: ProactiveEvent,
        decision: ProactiveDecision,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        category: NotificationCategory = NotificationCategory.SYSTEM,
        action: ProactiveAction | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProactiveNotification:
        """Create, sanitize, and store a new proactive notification."""
        clean_title = sanitize_text(event.title)
        clean_message = sanitize_text(message)

        notif = ProactiveNotification(
            title=clean_title,
            message=clean_message,
            event=event,
            priority=priority,
            decision=decision,
            category=category,
            status=NotificationStatus.PENDING,
            project_id=event.project_id,
            related_task_id=event.task_id,
            action=action,
            metadata=metadata or {},
        )

        self._notifications[notif.notification_id] = notif
        logger.info(
            "proactive_notification_created",
            notification_id=str(notif.notification_id),
            title=notif.title,
            priority=notif.priority.value,
            decision=notif.decision.value,
            category=notif.category.value,
        )
        return notif

    def get_notification(self, notification_id: uuid.UUID | str) -> ProactiveNotification | None:
        """Retrieve notification by ID."""
        key = uuid.UUID(str(notification_id))
        return self._notifications.get(key)

    def list_notifications(
        self,
        status: NotificationStatus | None = None,
        priority: NotificationPriority | None = None,
        category: NotificationCategory | None = None,
        project_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[ProactiveNotification]:
        """Query stored notifications with optional filters."""
        now = datetime.now(timezone.utc)
        results: list[ProactiveNotification] = []

        for notif in sorted(self._notifications.values(), key=lambda n: n.created_at, reverse=True):
            if status is not None and notif.status != status:
                continue
            if priority is not None and notif.priority != priority:
                continue
            if category is not None and notif.category != category:
                continue
            if project_id is not None and notif.project_id != project_id:
                continue

            results.append(notif)
            if len(results) >= limit:
                break

        return results

    def get_active_notifications(self) -> list[ProactiveNotification]:
        """
        Get pending or delivered notifications that are not currently snoozed.
        """
        now = datetime.now(timezone.utc)
        active = []
        for notif in self._notifications.values():
            if notif.status in (NotificationStatus.PENDING, NotificationStatus.DELIVERED):
                if notif.snooze_until is None or notif.snooze_until <= now:
                    active.append(notif)
        return active

    async def deliver_notification(
        self,
        notification_id: uuid.UUID | str,
        ws_send: WSSend | None = None,
    ) -> ProactiveNotification | None:
        """Mark notification as delivered and broadcast over WebSocket if provided."""
        notif = self.get_notification(notification_id)
        if not notif:
            return None

        notif.status = NotificationStatus.DELIVERED
        notif.delivered_at = datetime.now(timezone.utc)
        notif.updated_at = datetime.now(timezone.utc)

        if ws_send is not None:
            try:
                await ws_send({
                    "type": "PROACTIVE_NOTIFICATION",
                    "payload": {
                        "notification_id": str(notif.notification_id),
                        "title": notif.title,
                        "message": notif.message,
                        "priority": notif.priority.value,
                        "decision": notif.decision.value,
                        "category": notif.category.value,
                        "project_id": str(notif.project_id) if notif.project_id else None,
                        "related_task_id": str(notif.related_task_id) if notif.related_task_id else None,
                        "action": {
                            "tool_name": notif.action.tool_name,
                            "description": notif.action.description,
                            "params": notif.action.params,
                        } if notif.action else None,
                        "created_at": notif.created_at.isoformat(),
                    },
                })
            except Exception as e:
                logger.error("ws_broadcast_failed", error=str(e), notification_id=str(notif.notification_id))

        return notif

    def dismiss(self, notification_id: uuid.UUID | str, feedback_text: str | None = None) -> ProactiveNotification | None:
        """Dismiss a notification."""
        notif = self.get_notification(notification_id)
        if not notif:
            return None

        notif.status = NotificationStatus.DISMISSED
        notif.responded_at = datetime.now(timezone.utc)
        notif.updated_at = datetime.now(timezone.utc)

        self._feedback_log.append(
            UserFeedback(
                notification_id=notif.notification_id,
                action_type="dismiss",
                feedback_text=feedback_text,
            )
        )
        logger.info("proactive_notification_dismissed", notification_id=str(notif.notification_id))
        return notif

    def snooze(self, notification_id: uuid.UUID | str, duration_minutes: int = 15) -> ProactiveNotification | None:
        """Snooze a notification for a specified duration."""
        notif = self.get_notification(notification_id)
        if not notif:
            return None

        now = datetime.now(timezone.utc)
        notif.status = NotificationStatus.SNOOZED
        notif.snooze_until = now + timedelta(minutes=max(1, duration_minutes))
        notif.updated_at = now

        self._feedback_log.append(
            UserFeedback(
                notification_id=notif.notification_id,
                action_type="snooze",
                snooze_minutes=duration_minutes,
            )
        )
        logger.info("proactive_notification_snoozed", notification_id=str(notif.notification_id), snooze_minutes=duration_minutes)
        return notif

    def approve_action(self, notification_id: uuid.UUID | str) -> tuple[ProactiveNotification | None, ProactiveAction | None]:
        """Approve requested action for execution."""
        notif = self.get_notification(notification_id)
        if not notif or not notif.action:
            return None, None

        now = datetime.now(timezone.utc)
        notif.status = NotificationStatus.APPROVED
        notif.responded_at = now
        notif.updated_at = now

        self._feedback_log.append(
            UserFeedback(
                notification_id=notif.notification_id,
                action_type="approve",
            )
        )
        logger.info("proactive_action_approved", notification_id=str(notif.notification_id), tool=notif.action.tool_name)
        return notif, notif.action

    def reject_action(self, notification_id: uuid.UUID | str, reason: str | None = None) -> ProactiveNotification | None:
        """Reject requested action."""
        notif = self.get_notification(notification_id)
        if not notif:
            return None

        now = datetime.now(timezone.utc)
        notif.status = NotificationStatus.REJECTED
        notif.responded_at = now
        notif.updated_at = now

        self._feedback_log.append(
            UserFeedback(
                notification_id=notif.notification_id,
                action_type="reject",
                feedback_text=reason,
            )
        )
        logger.info("proactive_action_rejected", notification_id=str(notif.notification_id), reason=reason)
        return notif

    def mark_executed(self, notification_id: uuid.UUID | str) -> ProactiveNotification | None:
        """Mark notification action as successfully executed."""
        notif = self.get_notification(notification_id)
        if not notif:
            return None

        notif.status = NotificationStatus.EXECUTED
        notif.updated_at = datetime.now(timezone.utc)
        return notif

    def list_feedback_history(self) -> list[UserFeedback]:
        """Retrieve feedback interaction log."""
        return list(self._feedback_log)
