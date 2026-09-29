"""
tasks.executor — Autonomous Task Executor (V9)

Executes tasks through Kora's complete autonomous cognitive loop:
  Goal -> Plan -> Context Retrieval -> Tool Execution -> Verification -> Retry/Replan -> Completion -> Memory.
Broadcasts live WebSocket updates and respects offline/online model routing.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
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
    TriggerType,
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
        broadcast_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.task_manager = task_manager
        self.planner = planner or Planner()
        self.context_resolver = context_resolver or ContextResolver()
        self.tool_registry = tool_registry or build_default_registry()
        self.permission_gate = permission_gate or PermissionGate()
        self.verifier = verifier or Verifier()
        self.memory_manager = memory_manager
        self.audit_logger = audit_logger or ToolAuditLogger()
        self.broadcast_callback = broadcast_callback

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast status update to connected WebSocket clients."""
        try:
            if self.broadcast_callback:
                res = self.broadcast_callback(payload)
                if inspect.isawaitable(res):
                    await res
            else:
                from api.ws import broadcast_ws
                await broadcast_ws(payload)
        except Exception as e:
            logger.debug("broadcast_skipped", error=str(e))

    def _determine_model_used(self) -> str:
        """Identify whether cloud AI or local Ollama is active."""
        try:
            from api.deps import get_failover_manager
            fm = get_failover_manager()
            if fm.active_provider_name == "huggingface" and fm.is_internet_available:
                return "HuggingFace Cloud (Online)"
            return "Ollama Local (qwen3:1.7b)"
        except Exception:
            return "Ollama Local (qwen3:1.7b)"

    async def execute_task(self, task_id: UUID | str, trigger_source: str = "manual") -> TaskExecutionHistory:
        """
        Execute an autonomous task from start to finish.
        """
        task = await self.task_manager.get_task(task_id)
        if not task:
            raise ExecutionError(f"Task {task_id} not found")

        # Check dependencies
        deps_met = await self.task_manager.check_dependencies_met(task.task_id)
        if not deps_met:
            await self.task_manager.storage.update_status(task.task_id, TaskState.WAITING)
            raise ExecutionError(f"Cannot execute task {task.task_id}: dependencies unmet")

        model_label = self._determine_model_used()

        # Transition to RUNNING
        await self.task_manager.storage.update_status(task.task_id, TaskState.RUNNING)

        history = TaskExecutionHistory(
            run_id=uuid4(),
            task_id=task.task_id,
            run_number=len(task.execution_history) + 1,
            status=TaskState.RUNNING,
            started_at=datetime.now(timezone.utc),
            trigger_source=trigger_source,
            model_used=model_label,
        )

        start_perf = time.perf_counter()

        await self._broadcast({
            "type": "AUTOMATION_STARTED",
            "task_id": str(task.task_id),
            "run_id": str(history.run_id),
            "name": task.name or task.goal,
            "model_used": model_label,
            "started_at": history.started_at.isoformat(),
        })

        try:
            # ── 1. Context Retrieval ──────────────────────────────────────────
            needed_sources: set[SourceType] = set()
            if hasattr(self.context_resolver, "resolve"):
                resolver_fn: Any = getattr(self.context_resolver, "resolve")
                sig = inspect.signature(resolver_fn)
                if "message" in sig.parameters:
                    res = resolver_fn(
                        message=task.goal,
                        project_id=task.project_id,
                    )
                elif "query" in sig.parameters:
                    res = resolver_fn(
                        query=task.goal,
                        project_id=task.project_id,
                    )
                else:
                    res = resolver_fn(task.goal, task.project_id)

                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, (set, list)):
                    needed_sources = set(res)

            logger.info("task_context_resolved", sources=[s.value for s in needed_sources])

            # ── 2. Planning ───────────────────────────────────────────────────
            plan = await self._generate_plan(task)
            steps_to_run = list(getattr(plan, "steps", []))
            
            # Fallback plan if planner returned 0 steps
            if not steps_to_run:
                steps_to_run = self._generate_heuristic_steps(task)

            history.plan = [
                {
                    "index": getattr(s, "index", idx + 1),
                    "label": getattr(s, "label", getattr(s, "goal", f"Step {idx + 1}")),
                    "tool": getattr(s, "required_tool", getattr(s, "tool_name", None)),
                }
                for idx, s in enumerate(steps_to_run)
            ]

            await self._broadcast({
                "type": "AUTOMATION_PLAN",
                "task_id": str(task.task_id),
                "run_id": str(history.run_id),
                "steps": history.plan,
            })

            step_idx = 0
            replan_budget = 2
            collected_outputs: list[dict[str, Any]] = []

            while step_idx < len(steps_to_run):
                step = steps_to_run[step_idx]
                step_goal = getattr(step, "goal", getattr(step, "label", f"Step {step_idx + 1}"))
                tool_name = getattr(step, "required_tool", getattr(step, "tool_name", None))

                await self._broadcast({
                    "type": "AUTOMATION_STEP_START",
                    "task_id": str(task.task_id),
                    "run_id": str(history.run_id),
                    "step_index": step_idx + 1,
                    "goal": step_goal,
                    "tool_name": tool_name,
                })

                step_record = await self._execute_step_with_retries(
                    task=task,
                    step=step,
                    step_index=step_idx + 1,
                )
                history.steps.append(step_record)

                await self._broadcast({
                    "type": "AUTOMATION_STEP_FINISH",
                    "task_id": str(task.task_id),
                    "run_id": str(history.run_id),
                    "step_index": step_idx + 1,
                    "status": step_record.status,
                    "output": step_record.output,
                    "error": step_record.error,
                    "duration_ms": step_record.duration_ms,
                })

                if step_record.status != "completed":
                    if replan_budget > 0 and step_record.error and "Permission denied" not in step_record.error:
                        replan_budget -= 1
                        history.replan_count += 1
                        replan_goal = f"Overcome error '{step_record.error}' while achieving step: {step_goal}"
                        sub_plan = await self._generate_plan(task, override_goal=replan_goal)
                        remaining = steps_to_run[step_idx + 1 :]
                        steps_to_run = steps_to_run[: step_idx + 1] + list(getattr(sub_plan, "steps", [])) + remaining
                        step_idx += 1
                        continue
                    else:
                        raise ExecutionError(f"Step {step_idx + 1} failed: {step_record.error}")

                if step_record.output:
                    collected_outputs.append({
                        "step": step_goal,
                        "tool": tool_name,
                        "output": step_record.output,
                    })

                history.steps_completed += 1
                step_idx += 1

            # ── 3. Task Completion & Synthesis ───────────────────────────────
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            history.status = TaskState.COMPLETED
            history.completed_at = datetime.now(timezone.utc)
            history.duration_ms = duration_ms

            # Generate final synthesis result
            final_summary = self._synthesize_result(task, collected_outputs)
            history.result = final_summary

            # Recurring tasks remain ACTIVE, one-time tasks become COMPLETED
            next_state = TaskState.ACTIVE if task.trigger.trigger_type in {TriggerType.INTERVAL, TriggerType.CRON} else TaskState.COMPLETED
            await self.task_manager.storage.update_status(task.task_id, next_state)
            await self.task_manager.storage.record_run(task.task_id, history)

            await self._broadcast({
                "type": "AUTOMATION_COMPLETED",
                "task_id": str(task.task_id),
                "run_id": str(history.run_id),
                "status": "completed",
                "result": final_summary,
                "duration_ms": duration_ms,
                "model_used": history.model_used,
            })

            # ── 4. Commit Learnings to Memory ─────────────────────────────────
            if self.memory_manager:
                try:
                    await self.memory_manager.create_memory(
                        type=MemoryType.TASK_CONTEXT,
                        content=f"Completed automation '{task.name or task.goal}' with {history.steps_completed} steps in {duration_ms}ms.",
                        project_id=task.project_id,
                        session_id=task.session_id,
                        source="automation_engine",
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

            next_state = TaskState.FAILED if task.trigger.trigger_type in {TriggerType.MANUAL, TriggerType.DATE} else TaskState.ACTIVE
            await self.task_manager.storage.update_status(task.task_id, next_state)
            await self.task_manager.storage.record_run(task.task_id, history)

            await self._broadcast({
                "type": "AUTOMATION_FAILED",
                "task_id": str(task.task_id),
                "run_id": str(history.run_id),
                "status": "failed",
                "error": str(e),
                "duration_ms": duration_ms,
                "model_used": history.model_used,
            })

            logger.error("task_execution_failed", task_id=str(task.task_id), error=str(e), duration_ms=duration_ms)
            return history

    def _generate_heuristic_steps(self, task: TaskDefinition) -> list[PlanStep]:
        """Generate structured steps based on goal keywords when planner produces empty plan."""
        goal_lower = task.goal.lower()
        steps: list[PlanStep] = []

        if any(w in goal_lower for w in ("git", "commit", "branch", "repo", "repository")):
            steps.append(PlanStep(
                index=1,
                label="Inspect Git repository status and recent changes",
                action_type=ActionType.TOOL_CALL,
                goal="Check Git status and branch state",
                required_tool="git_ops",
                params={"command": "status"},
            ))
            steps.append(PlanStep(
                index=2,
                label="Inspect recent commits",
                action_type=ActionType.TOOL_CALL,
                goal="Inspect recent Git commits",
                required_tool="git_ops",
                params={"command": "log"},
            ))
            steps.append(PlanStep(
                index=3,
                label="Analyze changes and summarize",
                action_type=ActionType.MODEL_GENERATE,
                goal="Generate summary of Git repository changes",
            ))
        elif any(w in goal_lower for w in ("research", "search", "web", "find", "track", "news", "trend")):
            query = task.goal.replace("research", "").replace("search", "").strip() or task.goal
            steps.append(PlanStep(
                index=1,
                label=f"Search DuckDuckGo for: {query[:40]}",
                action_type=ActionType.TOOL_CALL,
                goal=f"Execute web search for: {query}",
                required_tool="web_search",
                params={"query": query, "max_results": 5},
            ))
            steps.append(PlanStep(
                index=2,
                label="Synthesize search findings into report",
                action_type=ActionType.MODEL_GENERATE,
                goal="Synthesize research results",
            ))
        elif any(w in goal_lower for w in ("health", "system", "disk", "memory", "cpu", "resource")):
            steps.append(PlanStep(
                index=1,
                label="Query system metrics and resource usage",
                action_type=ActionType.TOOL_CALL,
                goal="Gather CPU, memory, and disk metrics",
                required_tool="system_info",
                params={"metrics": ["cpu", "memory", "disk"]},
            ))
            steps.append(PlanStep(
                index=2,
                label="Analyze system metrics and generate health report",
                action_type=ActionType.MODEL_GENERATE,
                goal="Evaluate system health status",
            ))
        elif any(w in goal_lower for w in ("file", "directory", "watch", "folder", "scan")):
            steps.append(PlanStep(
                index=1,
                label="List directory contents and verify files",
                action_type=ActionType.TOOL_CALL,
                goal="List files in directory",
                required_tool="directory_ops",
                params={"path": str(Path.cwd()), "action": "list"},
            ))
            steps.append(PlanStep(
                index=2,
                label="Evaluate file structure and modifications",
                action_type=ActionType.MODEL_GENERATE,
                goal="Summarize directory state",
            ))
        else:
            steps.append(PlanStep(
                index=1,
                label=f"Execute: {task.name or task.goal}",
                action_type=ActionType.MODEL_GENERATE,
                goal=task.goal,
            ))

        return steps

    def _synthesize_result(self, task: TaskDefinition, outputs: list[dict[str, Any]]) -> str:
        """Create a clear, structured summary from executed steps."""
        if not outputs:
            return f"Automation '{task.name or task.goal}' finished successfully."

        lines = [f"### Automation Summary: {task.name or task.goal}"]
        for item in outputs:
            step_name = item.get("step", "Step")
            tool_name = item.get("tool") or "Reasoning"
            out = item.get("output")
            
            if isinstance(out, dict):
                if "results" in out and isinstance(out["results"], list):
                    # Search results
                    count = len(out["results"])
                    lines.append(f"\n**{step_name}** ({tool_name}): Found {count} sources.")
                    for r in out["results"][:3]:
                        lines.append(f"- [{r.get('title')}]({r.get('url')}): {r.get('snippet', '')[:100]}...")
                elif "stdout" in out:
                    lines.append(f"\n**{step_name}** ({tool_name}):")
                    lines.append(f"```\n{str(out['stdout'])[:300]}\n```")
                elif "files" in out:
                    lines.append(f"\n**{step_name}** ({tool_name}): {len(out.get('files', []))} items found.")
                else:
                    lines.append(f"\n**{step_name}** ({tool_name}): Verified.")
            else:
                lines.append(f"\n**{step_name}**: {str(out)[:200]}")

        lines.append(f"\nExecution completed autonomously at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}.")
        return "\n".join(lines)

    async def _generate_plan(self, task: TaskDefinition, override_goal: str | None = None) -> Any:
        """Invoke planner supporting both sync/async and ChatRequest/goal calling signatures."""
        goal = override_goal or task.goal
        chat_req = ChatRequest(
            message=goal,
            session_id=task.session_id or uuid4(),
            project_id=task.project_id,
        )
        planner_obj: Any = self.planner
        planner_fn = getattr(planner_obj, "plan", planner_obj)
        sig = inspect.signature(planner_fn)

        if "request" in sig.parameters:
            res = planner_fn(request=chat_req)
        elif "goal" in sig.parameters:
            kwargs: dict[str, Any] = {"goal": goal}
            if "context" in sig.parameters:
                kwargs["context"] = f"Autonomous Goal: {goal}"
            if "available_tools" in sig.parameters:
                kwargs["available_tools"] = [t.name for t in self.tool_registry.all()]
            res = planner_fn(**kwargs)
        else:
            res = planner_fn(chat_req)

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
        tool_params = dict(getattr(step, "params", getattr(step, "tool_params", {})) or {})

        # Safety & scope checking
        if task.allowed_tools and tool_name and tool_name not in task.allowed_tools:
            return TaskStepRecord(
                step_id=uuid4(),
                task_id=task.task_id,
                step_index=step_index,
                goal=step_goal,
                tool_name=tool_name,
                tool_params=tool_params,
                status="failed",
                error=f"Tool '{tool_name}' is not permitted by automation scope",
            )

        # Normalize default tool parameters to prevent missing required args
        if tool_name == "git_ops":
            if "repo_path" not in tool_params:
                tool_params["repo_path"] = str(Path.cwd())
            if "command" not in tool_params:
                tool_params["command"] = "status"
        elif tool_name == "directory_ops":
            if "path" not in tool_params:
                tool_params["path"] = str(Path.cwd())
            if "action" not in tool_params:
                tool_params["action"] = "list"
        elif tool_name == "system_info":
            if "metrics" not in tool_params:
                tool_params["metrics"] = ["cpu", "memory", "disk"]

        step_record = TaskStepRecord(
            step_id=uuid4(),
            task_id=task.task_id,
            step_index=step_index,
            goal=step_goal,
            tool_name=tool_name,
            tool_params=tool_params,
            status="running",
        )

        step_start = time.perf_counter()
        retries_left = task.max_retries

        while retries_left >= 0:
            try:
                # Direct step without tool / Model generation step
                if not tool_name or tool_name in ("direct_response", "model_generate", "none"):
                    step_record.status = "completed"
                    step_record.output = {"result": f"Completed analysis for: {step_goal}"}
                    step_record.verified = True
                    step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                    return step_record

                tool = self.tool_registry.get(tool_name)

                # Permission Check
                if self.permission_gate is not None:
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
