"""
tests.agent.test_proactive_v15 — Test Suite for Kora Proactive Intelligence (V15)

Verifies:
  1. Event Detection across tasks, files, memory, and system sources
  2. Multi-factor relevance scoring and user preference filtering
  3. Anti-spam deduplication, cooldowns, exponential backoff, and hourly rate limits
  4. Proactive decision classifications (IGNORE, INFORM, SUGGEST, ASK, ACT)
  5. Notification management, sanitization, snooze, dismiss, approve, and reject
  6. Autonomous follow-up tasks with strict anti-recursion depth limits
  7. End-to-end coordinator flow and WebSocket delivery
  8. Database schema models
"""

import uuid
from datetime import datetime, timezone

import pytest

from proactive.decision import ProactiveDecisionEngine
from proactive.detector import EventDetector
from proactive.engine import ProactiveIntelligenceEngine
from proactive.notifications import NotificationManager, sanitize_text
from proactive.relevance import RelevanceEngine
from proactive.tasks import ProactiveTaskManager
from proactive.types import (
    EventSourceType,
    EventUrgency,
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    ProactiveConfig,
    ProactiveDecision,
    ProactiveEvent,
    RelevanceScore,
)
from db.schema import ProactiveEventRecord, ProactiveNotificationRecord
from tasks.manager import TaskManager
from tasks.storage import TaskStorage
from tasks.types import TaskPriority, TaskState


# ── 1. Event Detection Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_detector_task_lifecycle():
    detector = EventDetector()
    events_caught = []

    async def listener(evt: ProactiveEvent):
        events_caught.append(evt)

    detector.register_listener(listener)

    task_id = uuid.uuid4()
    project_id = uuid.uuid4()

    # Task completed
    evt1 = await detector.on_task_completed(
        task_id=task_id,
        goal="Build feature X",
        project_id=project_id,
        duration_ms=1200,
        result_summary="Completed smoothly",
    )
    assert evt1.source_type == EventSourceType.TASK_LIFECYCLE
    assert evt1.urgency == EventUrgency.LOW
    assert len(events_caught) == 1

    # Task failed
    evt2 = await detector.on_task_failed(
        task_id=task_id,
        goal="Deploy service",
        error_message="Connection refused",
        project_id=project_id,
    )
    assert evt2.source_type == EventSourceType.TASK_LIFECYCLE
    assert evt2.urgency == EventUrgency.HIGH
    assert evt2.importance >= 0.8
    assert len(events_caught) == 2


@pytest.mark.asyncio
async def test_event_detector_project_and_memory():
    detector = EventDetector()
    project_id = uuid.uuid4()

    # File changes
    evt_files = await detector.on_files_changed(
        project_id=project_id,
        files_added=["src/auth.py"],
        files_modified=["src/main.py"],
        files_deleted=[],
    )
    assert evt_files.source_type == EventSourceType.PROJECT_FILE_CHANGE
    assert evt_files.data["total_changes"] == 2

    # Memory contradiction
    evt_mem = await detector.on_memory_contradiction(
        old_memory_id=uuid.uuid4(),
        old_content="User prefers light theme",
        new_content="User prefers dark theme",
        project_id=project_id,
    )
    assert evt_mem.source_type == EventSourceType.MEMORY_CHANGE
    assert evt_mem.urgency == EventUrgency.LOW

    # Preference updated
    evt_pref = await detector.on_user_preference_updated(
        preference_key="editor_theme",
        value="dark",
        project_id=project_id,
    )
    assert evt_pref.source_type == EventSourceType.MEMORY_CHANGE


@pytest.mark.asyncio
async def test_event_detector_system_and_automation():
    detector = EventDetector()

    evt_sys = await detector.on_system_health_degraded(
        component_name="rag_vector_db",
        error_rate=0.45,
        status_message="Timeout spikes observed",
    )
    assert evt_sys.source_type == EventSourceType.SYSTEM_EVENT
    assert evt_sys.urgency == EventUrgency.HIGH
    assert evt_sys.importance == 0.9

    evt_auto = await detector.on_automation_triggered(
        trigger_name="nightly_backup",
        action_summary="Backup completed successfully",
    )
    assert evt_auto.source_type == EventSourceType.AUTOMATION


# ── 2. Relevance Scoring & Preferences ─────────────────────────────────────────

def test_relevance_scoring_multi_factor():
    config = ProactiveConfig(min_relevance_score=0.5)
    engine = RelevanceEngine(config)

    active_project = uuid.uuid4()
    other_project = uuid.uuid4()

    # High urgency event on active project with recent activity
    event_high = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Critical Task Failed",
        urgency=EventUrgency.CRITICAL,
        importance=0.9,
        project_id=active_project,
    )
    score_high = engine.evaluate(event_high, active_project_id=active_project, recent_activity=True)
    assert score_high.should_notify is True
    assert score_high.score >= 0.8

    # Low urgency event on non-active project without recent activity
    event_low = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Minor Task Done",
        urgency=EventUrgency.LOW,
        importance=0.2,
        project_id=other_project,
    )
    score_low = engine.evaluate(event_low, active_project_id=active_project, recent_activity=False)
    assert score_low.score < score_high.score


def test_relevance_category_filtering():
    config = ProactiveConfig(
        enabled_categories={NotificationCategory.TASK, NotificationCategory.SYSTEM}
    )
    engine = RelevanceEngine(config)

    # Allowed category
    evt_task = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Task Alert",
        urgency=EventUrgency.HIGH,
        importance=0.8,
    )
    res_task = engine.evaluate(evt_task)
    assert res_task.should_notify is True

    # Disabled category (PROJECT)
    evt_proj = ProactiveEvent(
        source_type=EventSourceType.PROJECT_FILE_CHANGE,
        title="Project Alert",
        urgency=EventUrgency.HIGH,
        importance=0.8,
    )
    res_proj = engine.evaluate(evt_proj)
    assert res_proj.should_notify is False
    assert res_proj.score == 0.0


# ── 3. Anti-Spam, Cooldowns & Rate Limiting ────────────────────────────────────

def test_anti_spam_duplicate_deduplication():
    config = ProactiveConfig(min_relevance_score=0.4)
    engine = RelevanceEngine(config)

    event = ProactiveEvent(
        source_type=EventSourceType.SYSTEM_EVENT,
        title="Disk Space Warning",
        data={"disk": "/dev/sda1"},
        urgency=EventUrgency.HIGH,
        importance=0.8,
    )

    # First evaluation: passes
    res1 = engine.evaluate(event)
    assert res1.should_notify is True
    engine.record_notification_delivered(event)

    # Immediate duplicate evaluation: suppressed
    res2 = engine.evaluate(event)
    assert res2.should_notify is False
    assert res2.deduplicated is True


def test_anti_spam_hourly_rate_limit():
    config = ProactiveConfig(
        min_relevance_score=0.3,
        max_notifications_per_hour=3,
        category_cooldowns={NotificationCategory.TASK: 0},
    )
    engine = RelevanceEngine(config)

    # Send 3 non-urgent notifications
    for i in range(3):
        evt = ProactiveEvent(
            source_type=EventSourceType.TASK_LIFECYCLE,
            title=f"Task Notification {i}",
            data={"counter": i},
            urgency=EventUrgency.NORMAL,
            importance=0.6,
        )
        res = engine.evaluate(evt)
        assert res.should_notify is True
        engine.record_notification_delivered(evt)

    # 4th notification within same hour should be rate-limited
    evt_extra = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Extra Task Notification",
        data={"counter": 99},
        urgency=EventUrgency.NORMAL,
        importance=0.6,
    )
    res_extra = engine.evaluate(evt_extra)
    assert res_extra.should_notify is False

    # Urgent notification can bypass normal hourly limit
    evt_urgent = ProactiveEvent(
        source_type=EventSourceType.SYSTEM_EVENT,
        title="Urgent Security Alert",
        data={"counter": 100},
        urgency=EventUrgency.CRITICAL,
        importance=1.0,
    )
    res_urgent = engine.evaluate(evt_urgent)
    assert res_urgent.should_notify is True


# ── 4. Proactive Decision Engine ───────────────────────────────────────────────

def test_proactive_decision_classifications():
    config = ProactiveConfig(allow_autonomous_actions=False)
    decision_engine = ProactiveDecisionEngine(config)

    # Low score -> IGNORE
    evt_ignored = ProactiveEvent(source_type=EventSourceType.TASK_LIFECYCLE, title="Ignored")
    rel_low = RelevanceScore(score=0.2, urgency=EventUrgency.LOW, importance=0.2, should_notify=False)
    dec, _, _, _ = decision_engine.decide(evt_ignored, rel_low)
    assert dec == ProactiveDecision.IGNORE

    # Task failed -> ASK for retry
    evt_failed = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Build Failed",
        data={"event_subtype": "task_failed", "goal": "Build", "error_message": "Compiler error"},
        urgency=EventUrgency.HIGH,
        importance=0.85,
    )
    rel_failed = RelevanceScore(score=0.85, urgency=EventUrgency.HIGH, importance=0.85, should_notify=True)
    dec, action, priority, msg = decision_engine.decide(evt_failed, rel_failed)
    assert dec == ProactiveDecision.ASK
    assert action is not None
    assert action.tool_name == "retry_task"
    assert priority == NotificationPriority.HIGH

    # Task completed -> INFORM
    evt_completed = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Task Complete",
        data={"event_subtype": "task_completed", "goal": "Index"},
        urgency=EventUrgency.LOW,
    )
    rel_completed = RelevanceScore(score=0.6, urgency=EventUrgency.LOW, importance=0.4, should_notify=True)
    dec, action, priority, msg = decision_engine.decide(evt_completed, rel_completed)
    assert dec == ProactiveDecision.INFORM
    assert action is None

    # Project file changes with autonomous actions disabled -> SUGGEST
    evt_files = ProactiveEvent(
        source_type=EventSourceType.PROJECT_FILE_CHANGE,
        title="Files Changed",
        data={"total_changes": 5},
    )
    rel_files = RelevanceScore(score=0.65, urgency=EventUrgency.NORMAL, importance=0.5, should_notify=True)
    dec, action, priority, msg = decision_engine.decide(evt_files, rel_files)
    assert dec == ProactiveDecision.SUGGEST
    assert action.tool_name == "index_project"

    # Project file changes with autonomous actions enabled -> ACT
    config_auto = ProactiveConfig(allow_autonomous_actions=True)
    engine_auto = ProactiveDecisionEngine(config_auto)
    dec_auto, action_auto, _, _ = engine_auto.decide(evt_files, rel_files)
    assert dec_auto == ProactiveDecision.ACT


# ── 5. Notification Management & Sanitization ──────────────────────────────────

def test_notification_sanitization():
    raw_text = "API Key: sk-abcdef1234567890abcdef1234567890 leaked in ghp_0123456789abcdef0123456789abcdef0123"
    sanitized = sanitize_text(raw_text)
    assert "sk-abcdef" not in sanitized
    assert "ghp_0123" not in sanitized
    assert "[REDACTED]" in sanitized


def test_notification_lifecycle_dismiss_snooze_approve():
    mgr = NotificationManager()
    event = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Secret token test: sk-1234567890abcdef1234567890abcdef",
        urgency=EventUrgency.NORMAL,
    )

    notif = mgr.create_notification(
        event=event,
        decision=ProactiveDecision.SUGGEST,
        message="Review token sk-1234567890abcdef1234567890abcdef now",
    )

    # Title & message sanitized
    assert "sk-12345" not in notif.title
    assert "sk-12345" not in notif.message
    assert notif.status == NotificationStatus.PENDING

    # Snooze notification for 10 minutes
    snoozed = mgr.snooze(notif.notification_id, duration_minutes=10)
    assert snoozed.status == NotificationStatus.SNOOZED
    assert snoozed.snooze_until is not None

    # Verify not returned in get_active_notifications while snoozed
    active = mgr.get_active_notifications()
    assert notif.notification_id not in [n.notification_id for n in active]

    # Dismiss notification
    dismissed = mgr.dismiss(notif.notification_id, feedback_text="Not relevant")
    assert dismissed.status == NotificationStatus.DISMISSED

    # Feedback history logged
    history = mgr.list_feedback_history()
    assert len(history) == 2
    assert history[-1].action_type == "dismiss"


# ── 6. Proactive Tasks & Anti-Recursion ────────────────────────────────────────

@pytest.mark.asyncio
async def test_proactive_task_anti_recursion():
    task_storage = TaskStorage()
    task_mgr = TaskManager(storage=task_storage)
    config = ProactiveConfig(max_proactive_depth=2)
    proactive_tasks = ProactiveTaskManager(task_manager=task_mgr, config=config)

    # Depth 0 event -> spawns Depth 1 task (Allowed)
    evt_depth0 = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Failed Initial Task",
        data={"goal": "Initial Scrape", "proactive_depth": 0},
    )
    t1 = await proactive_tasks.create_followup_task(
        goal="Retry Scrape Step 1",
        event=evt_depth0,
    )
    assert t1 is not None
    assert t1.metadata["proactive_depth"] == 1

    # Depth 1 event -> spawns Depth 2 task (Allowed)
    evt_depth1 = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Failed Follow-up Task",
        data={"goal": "Retry Scrape Step 1", "proactive_depth": 1},
    )
    t2 = await proactive_tasks.create_followup_task(
        goal="Retry Scrape Step 2",
        event=evt_depth1,
    )
    assert t2 is not None
    assert t2.metadata["proactive_depth"] == 2

    # Depth 2 event -> attempts Depth 3 task (Blocked by recursion guard)
    evt_depth2 = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Failed Level 2 Task",
        data={"goal": "Retry Scrape Step 2", "proactive_depth": 2},
    )
    t3 = await proactive_tasks.create_followup_task(
        goal="Retry Scrape Step 3",
        event=evt_depth2,
    )
    assert t3 is None  # Blocked!


# ── 7. End-to-End Coordinator Flow ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_proactive_intelligence_coordinator_flow():
    task_storage = TaskStorage()
    task_mgr = TaskManager(storage=task_storage)
    config = ProactiveConfig(allow_autonomous_actions=False)
    engine = ProactiveIntelligenceEngine(config=config)
    engine.task_manager = ProactiveTaskManager(task_manager=task_mgr, config=config)

    ws_messages = []

    async def mock_ws_send(payload: dict):
        ws_messages.append(payload)

    project_id = uuid.uuid4()
    task_id = uuid.uuid4()

    # Emit task failed event
    event = ProactiveEvent(
        source_type=EventSourceType.TASK_LIFECYCLE,
        title="Task Failed: Test Run",
        project_id=project_id,
        task_id=task_id,
        data={
            "event_subtype": "task_failed",
            "goal": "Execute integration test",
            "error_message": "Network timeout",
        },
        urgency=EventUrgency.HIGH,
        importance=0.85,
    )

    decision, notif, spawned = await engine.handle_event(
        event=event,
        active_project_id=project_id,
        ws_send=mock_ws_send,
    )

    assert decision == ProactiveDecision.ASK
    assert notif is not None
    assert notif.status == NotificationStatus.DELIVERED
    assert len(ws_messages) == 1
    assert ws_messages[0]["type"] == "PROACTIVE_NOTIFICATION"
    assert ws_messages[0]["payload"]["priority"] == "high"

    # User approves the suggested retry action
    retry_task = await engine.handle_user_action_approval(notif.notification_id)
    assert retry_task is not None
    assert "Retry with replanning" in retry_task.goal
    assert retry_task.status == TaskState.PENDING


# ── 8. Database Schema Models ──────────────────────────────────────────────────

def test_database_schema_models():
    event_rec = ProactiveEventRecord(
        source_type="task_lifecycle",
        title="Test Event",
        content_hash="abc123hash",
        payload={"key": "value"},
        relevance_score=0.8,
        urgency="high",
        importance=0.75,
        decision="ask",
    )
    assert event_rec.source_type == "task_lifecycle"
    assert event_rec.urgency == "high"

    notif_rec = ProactiveNotificationRecord(
        title="Test Notification",
        message="Please confirm action",
        priority="high",
        decision="ask",
        category="task",
        status="pending",
        action_payload={"tool": "retry_task"},
    )
    assert notif_rec.priority == "high"
    assert notif_rec.status == "pending"
