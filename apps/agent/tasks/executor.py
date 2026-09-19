"""
tasks.executor — Autonomous Task Executor (V9)

Executes tasks through Kora's complete autonomous cognitive loop:
  Goal -> Plan -> Context Retrieval -> Tool Execution -> Verification -> Retry/Replan -> Completion -> Memory.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from core.context_resolver import ContextResolver
from core.planner import Plan, PlanStep, Planner
from core.types import ActionType, ChatRequest, ExecutorResult, SourceType, VerifierVerdict
from core.verifier import Verifier
from memory.manager import MemoryManager
from memory.types import MemoryType
from permissions.gate import PermissionDeniedError, PermissionGate
from tasks.manager import TaskManager
from tasks.types import (
    TaskDefinition,
    TaskExecutionHistory,
    TaskPriority,
    TaskState,
    TaskStepRecord,
)
from tools.audit import ToolAuditLogger, sanitize_audit_payload
from tools.registry import ToolRegistry, build_default_registry
from tools.types import PermissionLevel, ToolResult, ToolStatus

logger = structlog.get_logger(__name__)


class ExecutionError(Exception):
    """Base execution exception."""


class AutonomousTaskExecutor:
    """
    Executes autonomous tasks end-to-end with planning, context retrieval,
    tool execution, verification, automatic retries, and dynamic replanning.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        planner: Any | None = None,
        context_resolver: ContextResolver | None = None,
        tool_registry: ToolRegistry | None = None,
        permission_gate: PermissionGate | None = None,
        verifier: Verifier | None = None,
        memory_manager: MemoryManager | None = None,
        audit_logger: ToolAuditLogger | None = None,
    ) -> None:
        self.task_manager = task_manager
        self.planner = planner or Planner()
        self.context_resolver = context_resolver or ContextResolver()
        self.tool_registry = tool_registry or build_default_registry()
        self.permission_gate = permission_gate or PermissionGate()
        self.verifier = verifier or Verifier()
        self.memory_manager = memory_manager
        self.audit_logger = audit_logger or ToolAuditLogger()

    async def execute_task(self, task_id: UUID | str) -> TaskExecutionHistory:
        """
        Execute an autonomous task from start to finish.
        """
        task = await self.task_manager.get_task(task_id)
        if task.status in {TaskState.COMPLETED, TaskState.CANCELLED}:
            logger.info("task_already_finished", task_id=str(task.task_id), status=task.status.value)
            return task.execution_history[-1] if task.execution_history else TaskExecutionHistory(task_id=task.task_id)

        # Check dependencies
        deps_met = await self.task_manager.check_dependencies_met(task.task_id)
        if not deps_met:
            await self.task_manager.storage.update_status(task.task_id, TaskState.WAITING)
            raise ExecutionError(f"Cannot execute task {task.task_id}: dependencies unmet")

        # Transition to RUNNING
        await self.task_manager.storage.update_status(task.task_id, TaskState.RUNNING)

        history = TaskExecutionHistory(
            run_id=uuid4(),
            task_id=task.task_id,
            run_number=len(task.execution_history) + 1,
            status=TaskState.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        start_perf = time.perf_counter()

        try:
            # ── 1. Context Retrieval ──────────────────────────────────────────
            needed_sources: set[SourceType] = set()
            if hasattr(self.context_resolver, "resolve"):
                sig = inspect.signature(self.context_resolver.resolve)
                if "message" in sig.parameters:
                    needed_sources = self.context_resolver.resolve(
                        message=task.goal,
                        project_id=task.project_id,
                    )
                elif "query" in sig.parameters:
                    res = self.context_resolver.resolve(query=task.goal, project_id=task.project_id)
                    if asyncio.iscoroutine(res):
                        await res

            logger.info("task_context_resolved", sources=[s.value for s in needed_sources])

            # ── 2. Planning ───────────────────────────────────────────────────
            plan = await self._generate_plan(task)
            await self.task_manager.storage.update_status(task.task_id, TaskState.PLANNED)

            steps_to_run = list(getattr(plan, "steps", []))
            step_idx = 0
            replan_budget = 2

            while step_idx < len(steps_to_run):
                step = steps_to_run[step_idx]
                step_record = await self._execute_step_with_retries(
                    task=task,
                    step=step,
                    step_index=step_idx + 1,
                )
                history.steps.append(step_record)

                if step_record.status != "completed":
                    # Check if failure is replannable
                    if replan_budget > 0 and step_record.error and "Permission denied" not in step_record.error:
                        replan_budget -= 1
                        history.replan_count += 1
                        step_goal = getattr(step, "goal", getattr(step, "label", f"Step {step_idx + 1}"))
                        logger.warning(
                            "replanning_on_step_failure",
                            task_id=str(task.task_id),
                            failed_step=step_goal,
                            error=step_record.error,
                        )
                        # Generate recovery plan
                        replan_goal = f"Overcome error '{step_record.error}' while achieving step: {step_goal}"
                        sub_plan = await self._generate_plan(task, override_goal=replan_goal)
                        # Splice remaining steps with new sub-plan steps
                        remaining = steps_to_run[step_idx + 1 :]
                        steps_to_run = steps_to_run[: step_idx + 1] + list(getattr(sub_plan, "steps", [])) + remaining
                        step_idx += 1
                        continue
                    else:
                        raise ExecutionError(f"Step {step_idx + 1} failed: {step_record.error}")

                history.steps_completed += 1
                step_idx += 1

            # ── 3. Task Completion ────────────────────────────────────────────
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            history.status = TaskState.COMPLETED
            history.completed_at = datetime.now(timezone.utc)
            history.duration_ms = duration_ms

            await self.task_manager.storage.update_status(task.task_id, TaskState.COMPLETED)
            await self.task_manager.storage.record_run(task.task_id, history)

            # ── 4. Commit Learnings to Memory ─────────────────────────────────
            if self.memory_manager:
                try:
                    await self.memory_manager.create_memory(
                        type=MemoryType.TASK_CONTEXT,
                        content=f"Completed autonomous task '{task.goal}' with {history.steps_completed} steps in {duration_ms}ms.",
                        project_id=task.project_id,
                        session_id=task.session_id,
                        source="task_engine",
                        confidence=1.0,
                    )
                except Exception as mem_err:
                    logger.warning("failed_to_save_task_memory", error=str(mem_err))

            logger.info("task_execution_completed", task_id=str(task.task_id), duration_ms=duration_ms)
            return history

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            history.status = TaskState.FAILED
            history.completed_at = datetime.now(timezone.utc)
            history.duration_ms = duration_ms
            history.error = str(e)

            await self.task_manager.storage.update_status(task.task_id, TaskState.FAILED)
            await self.task_manager.storage.record_run(task.task_id, history)
            logger.error("task_execution_failed", task_id=str(task.task_id), error=str(e), duration_ms=duration_ms)
            return history

    async def _generate_plan(self, task: TaskDefinition, override_goal: str | None = None) -> Any:
        """Invoke planner supporting both sync/async and ChatRequest/goal calling signatures."""
        goal = override_goal or task.goal
        sig = inspect.signature(self.planner.plan)

        if "request" in sig.parameters:
            chat_req = ChatRequest(
                message=goal,
                session_id=task.session_id or uuid4(),
                project_id=task.project_id,
            )
            res = self.planner.plan(chat_req)
        elif "goal" in sig.parameters:
            res = self.planner.plan(
                goal=goal,
                context=f"Autonomous Goal: {goal}",
                available_tools=[t.name for t in self.tool_registry.all()],
            )
        else:
            res = self.planner.plan(goal)

        if asyncio.iscoroutine(res):
            return await res
        return res

    async def _execute_step_with_retries(
        self,
        task: TaskDefinition,
        step: Any,
        step_index: int,
    ) -> TaskStepRecord:
        """
        Execute a single plan step with exponential backoff retries and verification.
        """
        step_goal = getattr(step, "goal", getattr(step, "label", f"Step {step_index}"))
        tool_name = getattr(step, "required_tool", getattr(step, "tool_name", None))
        tool_params = getattr(step, "params", getattr(step, "tool_params", {}))

        step_record = TaskStepRecord(
            step_id=uuid4(),
            task_id=task.task_id,
            step_index=step_index,
            goal=step_goal,
            tool_name=tool_name,
            tool_params=tool_params or {},
            status="running",
        )

        step_start = time.perf_counter()
        retries_left = task.max_retries

        while retries_left >= 0:
            try:
                # Direct step without tool
                if not tool_name or tool_name == "direct_response":
                    step_record.status = "completed"
                    step_record.output = {"result": f"Executed step: {step_goal}"}
                    step_record.verified = True
                    step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                    return step_record

                tool = self.tool_registry.get(tool_name)

                # Permission Check
                if task.require_approval_for_tools:
                    await self.permission_gate.check(tool)

                # Tool Execution
                tool_res = await tool.run(tool_params)

                if not tool_res.success:
                    raise ExecutionError(tool_res.error or f"Tool {tool_name} failed")

                # Verification
                if hasattr(self.verifier, "check"):
                    exec_res = ExecutorResult(
                        step=step if isinstance(step, PlanStep) else PlanStep(index=step_index, label=step_goal, action_type=ActionType.TOOL_CALL),
                        success=tool_res.success,
                        content=str(tool_res.output or tool_res.error or ""),
                        raw=tool_res.output,
                        error=tool_res.error,
                    )
                    v_res = self.verifier.check(exec_res, attempt=task.max_retries - retries_left)
                    if asyncio.iscoroutine(v_res):
                        v_res = await v_res
                    if v_res == VerifierVerdict.RETRY:
                        raise ExecutionError("Verifier requested retry")
                    elif v_res == VerifierVerdict.ESCALATE:
                        raise ExecutionError("Verifier escalated failure")
                elif hasattr(self.verifier, "verify"):
                    v_res = self.verifier.verify(
                        step_goal=step_goal,
                        tool_output=tool_res.output,
                        tool_name=tool_name,
                    )
                    if hasattr(v_res, "success") and not v_res.success:
                        raise ExecutionError(f"Verification failed: {getattr(v_res, 'feedback', 'Unmet step criteria')}")

                step_record.status = "completed"
                step_record.output = tool_res.output
                step_record.verified = True
                step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                return step_record

            except PermissionDeniedError as pde:
                step_record.status = "failed"
                step_record.error = f"Permission denied: {pde}"
                step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                return step_record

            except Exception as ex:
                retries_left -= 1
                if retries_left < 0:
                    step_record.status = "failed"
                    step_record.error = str(ex)
                    step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                    return step_record

                # Exponential backoff (brief in async)
                backoff = min(0.05 * (2 ** (task.max_retries - retries_left)), 1.0)
                logger.warning(
                    "retrying_step_execution",
                    step_goal=step_goal,
                    tool=tool_name,
                    retries_left=retries_left,
                    backoff=backoff,
                    error=str(ex),
                )
                await asyncio.sleep(backoff)

        return step_record
