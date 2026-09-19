"""
tasks.automation — Automation & Scheduling Engine (V9)

Integrates APScheduler (AsyncIOScheduler), an internal asynchronous EventBus,
and condition evaluators to trigger tasks based on time, cron, events,
and task completion cascades.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from tasks.manager import TaskManager
from tasks.types import TaskDefinition, TaskState, TriggerConfig, TriggerType

logger = structlog.get_logger(__name__)


class EventBus:
    """Lightweight in-memory asynchronous event bus for event-driven triggers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Subscribe a coroutine callback to an event name."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Unsubscribe a callback."""
        if event_name in self._subscribers and callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)

    async def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Publish an event to all registered listeners asynchronously."""
        data = payload or {}
        handlers = list(self._subscribers.get(event_name, []))
        # Also notify wildcard subscribers
        handlers.extend(self._subscribers.get("*", []))

        logger.debug("event_published", event_name=event_name, subscribers=len(handlers))
        for handler in handlers:
            try:
                res = handler(event_name, data)
                if inspect.isawaitable(res):
                    asyncio.create_task(res)
            except Exception as e:
                logger.error("event_handler_failed", event_name=event_name, error=str(e))


class AutomationEngine:
    """
    Coordinates task scheduling via APScheduler and event-driven activations.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        executor_callback: Callable[[UUID | str], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self.task_manager = task_manager
        self.executor_callback = executor_callback
        self.scheduler = AsyncIOScheduler()
        self.event_bus = EventBus()
        self._running = False
        self._scheduled_jobs: dict[str, str] = {}  # task_id str -> job_id

    def start(self) -> None:
        """Start the APScheduler instance."""
        if not self.scheduler.running:
            self.scheduler.start()
            self._running = True
            logger.info("automation_engine_started")

    def shutdown(self, wait: bool = False) -> None:
        """Shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            self._running = False
            logger.info("automation_engine_shutdown")

    async def schedule_task(self, task: TaskDefinition) -> None:
        """
        Configure trigger and register task with scheduler or event bus.
        """
        task_id_str = str(task.task_id)
        trigger = task.trigger

        match trigger.trigger_type:
            case TriggerType.DATE:
                run_date = trigger.run_date or datetime.now(timezone.utc)
                job = self.scheduler.add_job(
                    self._on_trigger_fired,
                    trigger=DateTrigger(run_date=run_date),
                    args=[task.task_id],
                    id=f"job_{task_id_str}",
                    replace_existing=True,
                )
                self._scheduled_jobs[task_id_str] = job.id
                logger.info("scheduled_date_task", task_id=task_id_str, run_date=str(run_date))

            case TriggerType.INTERVAL:
                sec = trigger.interval_seconds or 60
                job = self.scheduler.add_job(
                    self._on_trigger_fired,
                    trigger=IntervalTrigger(seconds=sec),
                    args=[task.task_id],
                    id=f"job_{task_id_str}",
                    replace_existing=True,
                )
                self._scheduled_jobs[task_id_str] = job.id
                logger.info("scheduled_interval_task", task_id=task_id_str, interval_seconds=sec)

            case TriggerType.CRON:
                cron_expr = trigger.cron_expr or "0 * * * *"
                if isinstance(cron_expr, str):
                    parts = cron_expr.split()
                    if len(parts) == 5:
                        c_trigger = CronTrigger(
                            minute=parts[0],
                            hour=parts[1],
                            day=parts[2],
                            month=parts[3],
                            day_of_week=parts[4],
                        )
                    else:
                        c_trigger = CronTrigger.from_crontab(cron_expr)
                elif isinstance(cron_expr, dict):
                    c_trigger = CronTrigger(**cron_expr)
                else:
                    c_trigger = CronTrigger()

                job = self.scheduler.add_job(
                    self._on_trigger_fired,
                    trigger=c_trigger,
                    args=[task.task_id],
                    id=f"job_{task_id_str}",
                    replace_existing=True,
                )
                self._scheduled_jobs[task_id_str] = job.id
                logger.info("scheduled_cron_task", task_id=task_id_str, cron=str(cron_expr))

            case TriggerType.EVENT:
                event_name = trigger.event_name or f"task_{task_id_str}"
                self.event_bus.subscribe(
                    event_name,
                    lambda evt, payload, tid=task.task_id: self._on_event_fired(tid, evt, payload),
                )
                logger.info("subscribed_event_task", task_id=task_id_str, event_name=event_name)

            case TriggerType.TASK_COMPLETION:
                parent_id = str(trigger.parent_task_id) if trigger.parent_task_id else "any"
                evt_name = f"task_completed_{parent_id}"
                self.event_bus.subscribe(
                    evt_name,
                    lambda evt, payload, tid=task.task_id: self._on_event_fired(tid, evt, payload),
                )
                logger.info("subscribed_task_completion_cascade", task_id=task_id_str, parent_task_id=parent_id)

            case TriggerType.MANUAL:
                # Direct trigger; no scheduler job required
                pass

    async def unschedule_task(self, task_id: UUID | str) -> bool:
        """Remove scheduled job from scheduler."""
        task_id_str = str(task_id)
        job_id = self._scheduled_jobs.pop(task_id_str, None)
        if job_id and self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info("task_unscheduled", task_id=task_id_str)
            return True
        return False

    async def pause_schedule(self, task_id: UUID | str) -> bool:
        """Pause a scheduled job in APScheduler."""
        task_id_str = str(task_id)
        job_id = self._scheduled_jobs.get(task_id_str)
        if job_id and self.scheduler.get_job(job_id):
            self.scheduler.pause_job(job_id)
            logger.info("job_paused", task_id=task_id_str)
            return True
        return False

    async def resume_schedule(self, task_id: UUID | str) -> bool:
        """Resume a paused scheduled job."""
        task_id_str = str(task_id)
        job_id = self._scheduled_jobs.get(task_id_str)
        if job_id and self.scheduler.get_job(job_id):
            self.scheduler.resume_job(job_id)
            logger.info("job_resumed", task_id=task_id_str)
            return True
        return False

    async def dispatch_event(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Emit an event through the EventBus."""
        await self.event_bus.publish(event_name, payload)

    async def notify_task_finished(self, task_id: UUID | str, status: TaskState) -> None:
        """
        Called when a task finishes execution. Dispatches completion events
        to trigger dependent tasks.
        """
        task_id_str = str(task_id)
        if status == TaskState.COMPLETED:
            await self.dispatch_event(f"task_completed_{task_id_str}", {"task_id": task_id_str})
            await self.dispatch_event("task_completed_any", {"task_id": task_id_str})

    async def evaluate_condition(self, condition: str | dict[str, Any], context: dict[str, Any]) -> bool:
        """
        Evaluate a configurable condition against context data safely.
        Supports operator dicts like {"key": "status", "op": "==", "value": "active"}.
        """
        if isinstance(condition, dict):
            key = condition.get("key")
            op = condition.get("op", "==")
            expected = condition.get("value")
            actual = context.get(key) if key else None

            match op:
                case "==":
                    return actual == expected
                case "!=":
                    return actual != expected
                case ">":
                    return actual is not None and expected is not None and actual > expected
                case "<":
                    return actual is not None and expected is not None and actual < expected
                case "in":
                    return actual in expected if expected else False
                case _:
                    return False
        return True

    async def _on_trigger_fired(self, task_id: UUID) -> None:
        """Internal callback invoked when an APScheduler trigger fires."""
        logger.info("trigger_fired", task_id=str(task_id))
        # Verify dependencies before launching
        deps_met = await self.task_manager.check_dependencies_met(task_id)
        if not deps_met:
            logger.warning("trigger_postponed_dependencies_unmet", task_id=str(task_id))
            await self.task_manager.storage.update_status(task_id, TaskState.WAITING)
            return

        if self.executor_callback:
            res = self.executor_callback(task_id)
            if inspect.isawaitable(res):
                await res

    async def _on_event_fired(self, task_id: UUID, event_name: str, payload: dict[str, Any]) -> None:
        """Internal callback invoked when an EventBus event fires."""
        logger.info("event_trigger_fired", task_id=str(task_id), event_name=event_name)
        task = await self.task_manager.get_task(task_id)
        if task.trigger.condition_expr:
            cond_passed = await self.evaluate_condition(task.trigger.condition_expr, payload)
            if not cond_passed:
                logger.info("event_condition_not_met", task_id=str(task_id))
                return

        await self._on_trigger_fired(task_id)
