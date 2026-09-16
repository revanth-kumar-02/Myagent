import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable, Awaitable

from db.session import AsyncSessionLocal
from db.models import Task, TaskStep, ActivityLog
from core.state import ExecutionContext, AgentState, TaskStepState, StepExecutionState, validate_state_transition
from core.planner import TaskPlan, PlanStepSchema
from core.plan_validator import plan_validator
from core.recovery import FailureClassifier, FailureCategory, RecoveryStrategy
from core.tools.registry import tool_registry
from core.verifier import AgentVerifier
from core.filesystem.permission_manager import permission_manager
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

MAX_CONCURRENT_TASKS = 3

class DAGScheduler:
    """
    Dependency-Aware Asynchronous DAG Scheduler for Cocoa Agent.
    Manages concurrent step execution, dependency graphs, state machine transitions, cancellation, and WebSocket telemetry.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_TASKS):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # task_id -> dict of step_id -> asyncio.Task
        self.running_tasks: Dict[str, Dict[str, asyncio.Task]] = {}
        # task_id -> cancellation boolean flag
        self.cancelled_tasks: Set[str] = set()

    def is_cancelled(self, task_id: str) -> bool:
        return task_id in self.cancelled_tasks

    def cancel_task(self, task_id: str) -> bool:
        """Cancels an active task and all running step coroutines."""
        logger.info(f"Cancellation requested for task '{task_id}'")
        self.cancelled_tasks.add(task_id)
        if task_id in self.running_tasks:
            for step_id, sub_task in list(self.running_tasks[task_id].items()):
                if not sub_task.done():
                    sub_task.cancel()
        return True

    async def execute_dag_plan(
        self,
        ctx: ExecutionContext,
        plan: TaskPlan,
        verifier: AgentVerifier,
        executor_func: Callable[[StepExecutionState, ExecutionContext], Awaitable[Any]],
        on_activity: Optional[Callable[[str, str, dict], Awaitable[None]]] = None
    ) -> ExecutionContext:
        """
        Executes a TaskPlan respecting dependencies, parallelizing independent steps, and handling failures.
        """
        task_id = ctx.task_id
        self.cancelled_tasks.discard(task_id)
        self.running_tasks[task_id] = {}
        ctx.current_state = AgentState.EXECUTING
        ctx.started_at = datetime.utcnow().isoformat()

        # Build initial step execution states
        step_dict: Dict[str, StepExecutionState] = {}
        for idx, s in enumerate(plan.steps):
            s_state = StepExecutionState(
                step_id=s.id,
                step_number=idx + 1,
                title=s.title or s.description[:50],
                description=s.description,
                tool=s.tool,
                arguments=s.arguments or {},
                dependencies=s.dependencies or [],
                expected_outcome=s.expected_outcome,
                risk_level=s.risk_level,
                permission_level=s.permission_level,
                timeout=s.timeout,
                retry_policy=s.retry_policy or {"max_retries": 2},
                status=TaskStepState.PENDING
            )
            step_dict[s.id] = s_state

        ctx.steps = list(step_dict.values())

        # Emit task.planned event
        await ws_manager.broadcast({
            "event": "task.planned",
            "task_id": task_id,
            "status": "executing",
            "message": f"Execution plan initialized with {len(ctx.steps)} steps",
            "details": {"steps_count": len(ctx.steps)}
        })

        if on_activity:
            await on_activity("task.planned", f"Execution plan created ({len(ctx.steps)} steps)", {"count": len(ctx.steps)})

        # Build dependency graph
        dependencies: Dict[str, Set[str]] = {s_id: set(s.dependencies) for s_id, s in step_dict.items()}
        completed_steps: Set[str] = set()
        failed_steps: Set[str] = set()

        # Update initial states based on dependencies
        for s_id, s in step_dict.items():
            if not dependencies[s_id]:
                s.status = TaskStepState.READY
                await ws_manager.broadcast({
                    "event": "task.step.ready",
                    "task_id": task_id,
                    "step_id": s_id,
                    "tool": s.tool,
                    "status": "ready",
                    "message": f"Step {s.step_number} '{s.title}' is ready for execution"
                })
            else:
                s.status = TaskStepState.WAITING_DEPENDENCY

        # Main execution loop
        while len(completed_steps) + len(failed_steps) < len(step_dict):
            if self.is_cancelled(task_id):
                logger.info(f"Task '{task_id}' was cancelled during execution.")
                ctx.current_state = AgentState.CANCELLED
                await ws_manager.broadcast({
                    "event": "task.cancelled",
                    "task_id": task_id,
                    "status": "cancelled",
                    "message": "Task execution was cancelled by user request"
                })
                for s in step_dict.values():
                    if s.status not in (TaskStepState.COMPLETED, TaskStepState.FAILED):
                        s.status = TaskStepState.CANCELLED
                return ctx

            # Find all READY steps
            ready_steps = [s for s in step_dict.values() if s.status == TaskStepState.READY]

            if not ready_steps:
                # Check if any steps are still RUNNING or VERIFYING
                active_steps = [s for s in step_dict.values() if s.status in (TaskStepState.RUNNING, TaskStepState.VERIFYING, TaskStepState.WAITING_PERMISSION)]
                if not active_steps:
                    # Deadlock or unresolvable dependencies due to failures
                    logger.warning("No ready or active steps remaining in DAG execution loop.")
                    break
                await asyncio.sleep(0.1)
                continue

            # Launch ready steps concurrently
            async def run_single_step(step: StepExecutionState):
                async with self.semaphore:
                    if self.is_cancelled(task_id):
                        step.status = TaskStepState.CANCELLED
                        return

                    step.status = TaskStepState.RUNNING
                    await ws_manager.broadcast({
                        "event": "task.step.started",
                        "task_id": task_id,
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "status": "running",
                        "message": f"Step {step.step_number} '{step.title}' started running"
                    })

                    if on_activity:
                        await on_activity("step.started", f"Starting Step {step.step_number}: {step.title}", {"step_id": step.step_id})

                    # Permission Check
                    perm_ok = await permission_manager.check_permission(
                        tool_name=step.tool or "web_search",
                        path=step.arguments.get("path") or step.arguments.get("working_directory") or "",
                        operation=step.title,
                        permission_level=step.permission_level,
                        task_id=task_id,
                        project_id=ctx.project_id
                    )

                    if not perm_ok:
                        step.status = TaskStepState.FAILED
                        step.error = f"Permission denied for operation '{step.title}' ({step.permission_level})"
                        failed_steps.add(step.step_id)
                        await ws_manager.broadcast({
                            "event": "task.step.failed",
                            "task_id": task_id,
                            "step_id": step.step_id,
                            "tool": step.tool,
                            "status": "failed",
                            "error_category": FailureCategory.PERMISSION.value,
                            "message": f"Step {step.step_number} denied permission ({step.permission_level})"
                        })
                        return


                    # Execute tool coroutine
                    try:
                        res = await asyncio.wait_for(executor_func(step, ctx), timeout=step.timeout)
                        
                        # Verify step result
                        step.status = TaskStepState.VERIFYING
                        verification = await verifier.verify_step(ctx.goal, step.title, res.data if getattr(res, "success", False) else getattr(res, "error", str(res)))

                        if getattr(res, "success", False) and verification.success:
                            step.status = TaskStepState.COMPLETED
                            step.result = str(res.data)
                            completed_steps.add(step.step_id)
                            ctx.observations.append({"step_id": step.step_id, "title": step.title, "output": res.data})

                            await ws_manager.broadcast({
                                "event": "task.step.completed",
                                "task_id": task_id,
                                "step_id": step.step_id,
                                "tool": step.tool,
                                "status": "completed",
                                "duration": 1.0,
                                "message": f"Step {step.step_number} completed and verified successfully"
                            })

                            if on_activity:
                                await on_activity("step.completed", f"Step {step.step_number} completed", {"result": str(res.data)[:100]})

                            # Unblock downstream dependencies
                            for other_id, other_step in step_dict.items():
                                if other_step.status == TaskStepState.WAITING_DEPENDENCY:
                                    # Check if all dependencies for other_step are now in completed_steps
                                    if all(dep in completed_steps for dep in other_step.dependencies):
                                        other_step.status = TaskStepState.READY
                                        await ws_manager.broadcast({
                                            "event": "task.step.ready",
                                            "task_id": task_id,
                                            "step_id": other_id,
                                            "tool": other_step.tool,
                                            "status": "ready",
                                            "message": f"Step {other_step.step_number} '{other_step.title}' dependencies resolved, now ready"
                                        })

                        else:
                            fail_err = verification.reason if getattr(res, "success", False) else getattr(res, "error", "Execution failed")
                            cat = FailureClassifier.classify(fail_err, step.tool or "web_search", getattr(res, "data", None))
                            step.status = TaskStepState.FAILED
                            step.error = fail_err
                            failed_steps.add(step.step_id)

                            await ws_manager.broadcast({
                                "event": "task.step.failed",
                                "task_id": task_id,
                                "step_id": step.step_id,
                                "tool": step.tool,
                                "status": "failed",
                                "error_category": cat.value,
                                "message": f"Step {step.step_number} failed: {fail_err}"
                            })

                    except asyncio.TimeoutError:
                        step.status = TaskStepState.FAILED
                        step.error = f"Step execution timed out after {step.timeout}s"
                        failed_steps.add(step.step_id)
                        await ws_manager.broadcast({
                            "event": "task.step.failed",
                            "task_id": task_id,
                            "step_id": step.step_id,
                            "tool": step.tool,
                            "status": "failed",
                            "error_category": FailureCategory.TIMEOUT.value,
                            "message": f"Step {step.step_number} execution timed out"
                        })
                    except Exception as ex:
                        step.status = TaskStepState.FAILED
                        step.error = str(ex)
                        failed_steps.add(step.step_id)
                        await ws_manager.broadcast({
                            "event": "task.step.failed",
                            "task_id": task_id,
                            "step_id": step.step_id,
                            "tool": step.tool,
                            "status": "failed",
                            "error_category": FailureCategory.UNKNOWN.value,
                            "message": f"Step {step.step_number} failed with error: {ex}"
                        })

            tasks = []
            for s in ready_steps:
                sub_t = asyncio.create_task(run_single_step(s))
                self.running_tasks[task_id][s.step_id] = sub_t
                tasks.append(sub_t)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        if self.is_cancelled(task_id):
            ctx.current_state = AgentState.CANCELLED
            return ctx

        if failed_steps:
            ctx.current_state = AgentState.FAILED
            ctx.error_message = f"{len(failed_steps)} step(s) failed during execution."
        else:
            ctx.current_state = AgentState.COMPLETED
            ctx.completed_at = datetime.utcnow().isoformat()

        return ctx

    async def recover_interrupted_tasks(self):
        """Scans database on application startup to safely recover interrupted long-running tasks."""
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy.future import select
                stmt = select(Task).where(Task.status.in_(["planning", "executing", "running"]))
                res = await db.execute(stmt)
                tasks = res.scalars().all()
                for task in tasks:
                    logger.info(f"[RECOVERY] Resetting interrupted task '{task.id}' state from '{task.status}' to 'pending'.")
                    task.status = "pending"
                await db.commit()
        except Exception as e:
            logger.error(f"[RECOVERY] Task recovery scan error: {e}")

dag_scheduler = DAGScheduler()
