"""
tests.agent.test_automation_v9 — Comprehensive Test Suite for Autonomous Task & Automation Engine (V9)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from core.context_resolver import ContextResolver
from core.planner import Plan, PlanStep, Planner
from core.types import ActionType, SourceType, StepStatus, VerifierVerdict
from core.verifier import Verifier
from memory.manager import MemoryManager
from memory.types import MemoryType
from permissions.gate import PermissionDeniedError, PermissionGate
from tasks.automation import AutomationEngine, EventBus
from tasks.executor import AutonomousTaskExecutor, ExecutionError
from tasks.manager import (
    DependencyUnmetError,
    DuplicateTaskError,
    TaskManager,
    TaskManagerError,
    TaskNotFoundError,
)
from tasks.storage import TaskStorage
from tasks.types import (
    TaskDefinition,
    TaskExecutionHistory,
    TaskPriority,
    TaskState,
    TaskStepRecord,
    TriggerConfig,
    TriggerType,
)
from tools.audit import ToolAuditLogger, sanitize_audit_payload
from tools.base import BaseTool
from tools.registry import ToolRegistry, build_default_registry
from tools.scheduler import (
    CancelTaskTool,
    ListTasksTool,
    PauseTaskTool,
    ResumeTaskTool,
    ScheduleTaskTool,
)
from tools.types import PermissionLevel, ToolCategory, ToolResult, ToolStatus


# ── 1. Task Manager & State Transitions ──────────────────────────────────────


@pytest.mark.asyncio
class TestTaskManagerAndStateTransitions:

    async def test_task_creation_and_defaults(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(
            goal="Analyze daily metrics",
            priority=TaskPriority.HIGH,
            timeout_seconds=120,
        )

        assert isinstance(task.task_id, UUID)
        assert task.goal == "Analyze daily metrics"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskState.PENDING
        assert task.timeout_seconds == 120
        assert task.is_active is True
        assert task.is_terminal is False

    async def test_duplicate_task_prevention(self) -> None:
        manager = TaskManager()
        await manager.create_task(goal="Sync project files")

        # Creating an active duplicate should raise DuplicateTaskError
        with pytest.raises(DuplicateTaskError):
            await manager.create_task(goal="Sync project files")

        # Creating with allow_duplicates=True should succeed
        task2 = await manager.create_task(goal="Sync project files", allow_duplicates=True)
        assert task2.goal == "Sync project files"

    async def test_pause_resume_and_cancellation(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(goal="Run backup batch")

        # Pause
        paused = await manager.pause_task(task.task_id)
        assert paused.status == TaskState.PAUSED

        # Resume
        resumed = await manager.resume_task(task.task_id)
        assert resumed.status == TaskState.PENDING

        # Cancel
        cancelled = await manager.cancel_task(task.task_id, reason="User requested abort")
        assert cancelled.status == TaskState.CANCELLED
        assert cancelled.is_terminal is True
        assert cancelled.metadata["cancellation_reason"] == "User requested abort"

    async def test_dependency_checking(self) -> None:
        manager = TaskManager()
        dep1 = await manager.create_task(goal="Prerequisite Task 1")
        dep2 = await manager.create_task(goal="Prerequisite Task 2")

        main_task = await manager.create_task(
            goal="Main Aggregator Task",
            dependencies=[dep1.task_id, dep2.task_id],
        )

        # Initially dependencies not met
        assert await manager.check_dependencies_met(main_task.task_id) is False

        # Mark dep1 completed
        await manager.storage.update_status(dep1.task_id, TaskState.COMPLETED)
        assert await manager.check_dependencies_met(main_task.task_id) is False

        # Mark dep2 completed
        await manager.storage.update_status(dep2.task_id, TaskState.COMPLETED)
        assert await manager.check_dependencies_met(main_task.task_id) is True

    async def test_startup_crash_recovery(self) -> None:
        storage = TaskStorage()
        t1 = TaskDefinition(task_id=uuid4(), goal="Abandoned Task 1", status=TaskState.RUNNING)
        t2 = TaskDefinition(task_id=uuid4(), goal="Abandoned Task 2", status=TaskState.PLANNED)
        t3 = TaskDefinition(task_id=uuid4(), goal="Finished Task", status=TaskState.COMPLETED)

        await storage.save_task(t1)
        await storage.save_task(t2)
        await storage.save_task(t3)

        manager = TaskManager(storage=storage)
        recovered = await manager.recover_on_startup()
        assert recovered == 2

        t1_after = await manager.get_task(t1.task_id)
        t2_after = await manager.get_task(t2.task_id)
        t3_after = await manager.get_task(t3.task_id)

        assert t1_after.status == TaskState.PENDING
        assert t1_after.metadata.get("recovered_after_crash") is True
        assert t2_after.status == TaskState.PENDING
        assert t3_after.status == TaskState.COMPLETED


# ── 2. Automation Engine & Triggers ───────────────────────────────────────────


@pytest.mark.asyncio
class TestAutomationEngineTriggers:

    async def test_event_bus_and_event_trigger(self) -> None:
        manager = TaskManager()
        executed_tasks: list[UUID] = []

        async def mock_executor(tid: UUID | str) -> None:
            executed_tasks.append(UUID(str(tid)))

        auto_engine = AutomationEngine(task_manager=manager, executor_callback=mock_executor)

        task = await manager.create_task(
            goal="Trigger on GitHub push",
            trigger=TriggerConfig(
                trigger_type=TriggerType.EVENT,
                event_name="github_push",
            ),
        )

        await auto_engine.schedule_task(task)

        # Dispatch event
        await auto_engine.dispatch_event("github_push", {"branch": "main"})
        await asyncio.sleep(0.05)

        assert task.task_id in executed_tasks

    async def test_task_completion_cascade(self) -> None:
        manager = TaskManager()
        executed_tasks: list[UUID] = []

        async def mock_executor(tid: UUID | str) -> None:
            executed_tasks.append(UUID(str(tid)))

        auto_engine = AutomationEngine(task_manager=manager, executor_callback=mock_executor)

        parent_task = await manager.create_task(goal="Build Package")
        child_task = await manager.create_task(
            goal="Deploy Package",
            trigger=TriggerConfig(
                trigger_type=TriggerType.TASK_COMPLETION,
                parent_task_id=parent_task.task_id,
            ),
        )

        await auto_engine.schedule_task(child_task)

        # When parent task finishes
        await auto_engine.notify_task_finished(parent_task.task_id, TaskState.COMPLETED)
        await asyncio.sleep(0.05)

        assert child_task.task_id in executed_tasks

    async def test_configurable_condition_evaluation(self) -> None:
        manager = TaskManager()
        auto_engine = AutomationEngine(task_manager=manager)

        cond = {"key": "status_code", "op": "==", "value": 200}
        assert await auto_engine.evaluate_condition(cond, {"status_code": 200}) is True
        assert await auto_engine.evaluate_condition(cond, {"status_code": 500}) is False

        cond_gt = {"key": "cpu_pct", "op": ">", "value": 85}
        assert await auto_engine.evaluate_condition(cond_gt, {"cpu_pct": 92}) is True
        assert await auto_engine.evaluate_condition(cond_gt, {"cpu_pct": 50}) is False

    async def test_apscheduler_schedule_and_unschedule(self) -> None:
        manager = TaskManager()
        auto_engine = AutomationEngine(task_manager=manager)
        auto_engine.start()

        task = await manager.create_task(
            goal="Hourly report",
            trigger=TriggerConfig(
                trigger_type=TriggerType.INTERVAL,
                interval_seconds=3600,
            ),
        )

        await auto_engine.schedule_task(task)
        assert str(task.task_id) in auto_engine._scheduled_jobs

        # Pause and resume
        assert await auto_engine.pause_schedule(task.task_id) is True
        assert await auto_engine.resume_schedule(task.task_id) is True

        # Unschedule
        assert await auto_engine.unschedule_task(task.task_id) is True
        assert str(task.task_id) not in auto_engine._scheduled_jobs

        auto_engine.shutdown(wait=False)


# ── 3. Autonomous Execution Loop ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestAutonomousExecutionLoop:

    async def test_autonomous_task_success_lifecycle(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(goal="Create greeting and write file")

        # Mock Planner
        planner = MagicMock()
        planner.plan.return_value = Plan(
            steps=[
                PlanStep(index=0, label="Read system info", action_type=ActionType.TOOL_CALL, required_tool="system_info", params={}, goal="Read system info"),
                PlanStep(index=1, label="Write greeting to clipboard", action_type=ActionType.TOOL_CALL, required_tool="clipboard", params={"action": "write", "text": "Hello Autonomous World"}, goal="Write greeting to clipboard"),
            ],
            trace_id=uuid4(),
        )

        # Mock Memory Manager
        mock_memory = MagicMock()
        mock_memory.create_memory = AsyncMock()

        executor = AutonomousTaskExecutor(
            task_manager=manager,
            planner=planner,
            memory_manager=mock_memory,
        )

        history = await executor.execute_task(task.task_id)

        assert history.status == TaskState.COMPLETED
        assert history.steps_completed == 2
        assert len(history.steps) == 2
        assert history.steps[0].status == "completed"
        assert history.steps[1].status == "completed"

        # Check task state in storage
        updated_task = await manager.get_task(task.task_id)
        assert updated_task.status == TaskState.COMPLETED
        assert len(updated_task.execution_history) == 1

        # Check memory persistence called
        mock_memory.create_memory.assert_awaited_once()

    async def test_step_failure_and_exponential_backoff_retry(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(goal="Flaky Network Task", max_retries=2)

        # Tool that fails twice then succeeds
        attempts = 0

        class FlakyTool(BaseTool):
            @property
            def tool_id(self) -> str:
                return "flaky_tool"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.SYSTEM

            @property
            def description(self) -> str:
                return "Flaky test tool"

            @property
            def permission_level(self) -> PermissionLevel:
                return PermissionLevel.READ

            @property
            def parameters(self) -> dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def execute(self, params: dict[str, Any]) -> ToolResult:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    return self._make_result(error="Temporary network timeout")
                return self._make_result(output={"status": "ok", "attempts": attempts})

        registry = ToolRegistry()
        registry.register(FlakyTool())

        planner = MagicMock()
        planner.plan.return_value = Plan(
            steps=[PlanStep(index=0, label="Run flaky tool", action_type=ActionType.TOOL_CALL, required_tool="flaky_tool", params={}, goal="Run flaky tool")],
            trace_id=uuid4(),
        )

        executor = AutonomousTaskExecutor(
            task_manager=manager,
            planner=planner,
            tool_registry=registry,
        )

        history = await executor.execute_task(task.task_id)
        assert history.status == TaskState.COMPLETED
        assert attempts == 3
        assert history.steps[0].status == "completed"

    async def test_dynamic_replanning_on_unrecoverable_step(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(goal="Task needing replan")

        # Step 1 fails, trigger replan with alternative Step 2
        call_count = 0

        class FailingTool(BaseTool):
            @property
            def tool_id(self) -> str:
                return "failing_tool"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.SYSTEM

            @property
            def description(self) -> str:
                return "Fails permanently"

            @property
            def permission_level(self) -> PermissionLevel:
                return PermissionLevel.READ

            @property
            def parameters(self) -> dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def execute(self, params: dict[str, Any]) -> ToolResult:
                return self._make_result(error="Resource permanently unavailable")

        class FallbackTool(BaseTool):
            @property
            def tool_id(self) -> str:
                return "fallback_tool"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.SYSTEM

            @property
            def description(self) -> str:
                return "Fallback success tool"

            @property
            def permission_level(self) -> PermissionLevel:
                return PermissionLevel.READ

            @property
            def parameters(self) -> dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def execute(self, params: dict[str, Any]) -> ToolResult:
                return self._make_result(output={"fallback": "success"})

        registry = ToolRegistry()
        registry.register(FailingTool())
        registry.register(FallbackTool())

        planner = MagicMock()

        def mock_plan(goal: str, **kwargs) -> Plan:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Plan(
                    steps=[PlanStep(index=0, label="Try failing tool", action_type=ActionType.TOOL_CALL, required_tool="failing_tool", params={}, goal="Try failing tool")],
                    trace_id=uuid4(),
                )
            else:
                # Replanned sub-plan
                return Plan(
                    steps=[PlanStep(index=1, label="Try fallback tool", action_type=ActionType.TOOL_CALL, required_tool="fallback_tool", params={}, goal="Try fallback tool")],
                    trace_id=uuid4(),
                )

        planner.plan.side_effect = mock_plan

        executor = AutonomousTaskExecutor(
            task_manager=manager,
            planner=planner,
            tool_registry=registry,
        )

        history = await executor.execute_task(task.task_id)
        assert history.status == TaskState.COMPLETED
        assert history.replan_count == 1
        assert len(history.steps) == 2
        assert history.steps[0].status == "failed"
        assert history.steps[1].status == "completed"


# ── 4. Safety & Secret Scrubbing ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestSafetyAndSecretScrubbing:

    async def test_permission_denial_halts_task_cleanly(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(goal="Delete critical system path")

        # Headless gate without WS raises PermissionDeniedError
        gate = PermissionGate(ws_send=None)

        planner = MagicMock()
        planner.plan.return_value = Plan(
            steps=[PlanStep(index=0, label="Delete file", action_type=ActionType.TOOL_CALL, required_tool="file_delete", params={"path": "/critical/file.txt"}, goal="Delete file")],
            trace_id=uuid4(),
        )

        executor = AutonomousTaskExecutor(
            task_manager=manager,
            planner=planner,
            permission_gate=gate,
        )

        history = await executor.execute_task(task.task_id)
        assert history.status == TaskState.FAILED
        assert "Permission denied" in str(history.error)

    async def test_secret_scrubbing_in_task_history(self) -> None:
        manager = TaskManager()
        task = await manager.create_task(
            goal="Authenticate external service",
            metadata={"api_key": "sk-super-secret-key-12345", "user": "admin"},
        )

        # Metadata should be scrubbed upon storage
        assert task.metadata["api_key"] == "****** [REDACTED SECRET]"

        # Record history with secrets
        history = TaskExecutionHistory(
            task_id=task.task_id,
            steps=[
                TaskStepRecord(
                    goal="Login",
                    tool_params={"password": "my_master_password", "user": "alice"},
                    output={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret"},
                )
            ],
        )

        await manager.storage.record_run(task.task_id, history)
        saved_task = await manager.get_task(task.task_id)
        saved_step = saved_task.execution_history[0].steps[0]

        assert saved_step.tool_params["password"] == "****** [REDACTED SECRET]"
        assert saved_step.output["token"] == "****** [REDACTED SECRET]"


# ── 5. Scheduler Tools ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSchedulerTools:

    async def test_schedule_task_tool(self) -> None:
        manager = TaskManager()
        auto_engine = AutomationEngine(task_manager=manager)
        auto_engine.start()

        sched_tool = ScheduleTaskTool(task_manager=manager, automation_engine=auto_engine)
        res = await sched_tool.run({
            "goal": "Generate weekly report",
            "trigger_type": "interval",
            "trigger_params": {"interval_seconds": 1800},
            "priority": "high",
        })

        assert res.success is True
        assert res.output["goal"] == "Generate weekly report"
        assert res.output["priority"] == "high"
        assert res.output["trigger_type"] == "interval"

        # List Tasks Tool
        list_tool = ListTasksTool(task_manager=manager)
        l_res = await list_tool.run({})
        assert l_res.success is True
        assert l_res.output["count"] >= 1

        # Pause Task Tool
        task_id = res.output["task_id"]
        pause_tool = PauseTaskTool(task_manager=manager, automation_engine=auto_engine)
        p_res = await pause_tool.run({"task_id": task_id})
        assert p_res.success is True
        assert p_res.output["status"] == "paused"

        # Resume Task Tool
        resume_tool = ResumeTaskTool(task_manager=manager, automation_engine=auto_engine)
        r_res = await resume_tool.run({"task_id": task_id})
        assert r_res.success is True
        assert r_res.output["status"] == "pending"

        # Cancel Task Tool
        cancel_tool = CancelTaskTool(task_manager=manager, automation_engine=auto_engine)
        c_res = await cancel_tool.run({"task_id": task_id, "reason": "No longer needed"})
        assert c_res.success is True
        assert c_res.output["status"] == "cancelled"

        auto_engine.shutdown(wait=False)
