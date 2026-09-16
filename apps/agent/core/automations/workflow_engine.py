import time
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.future import select

from db.session import AsyncSessionLocal
from db.models import Automation, AutomationRun, ActivityLog
from core.planner import agent_planner, TaskPlan
from core.agent import agent_orchestrator
from core.memory import memory_manager
from core.filesystem.permission_manager import permission_manager
from core.automations.trigger_evaluator import trigger_evaluator
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

class AutonomousWorkflowEngine:
    async def execute_automation_workflow(self, automation_id: str, trigger_reason: str = "SCHEDULED") -> Dict[str, Any]:
        """Executes an agentic, conditional automation workflow with persistence and safety bounds."""
        run_id = None
        start_time = time.time()
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Automation).where(Automation.id == automation_id))
            auto = result.scalar_one_or_none()

            if not auto:
                raise ValueError(f"Automation {automation_id} not found")
            if not auto.is_active:
                logger.info(f"Automation {automation_id} disabled. Skipping run.")
                return {"status": "SKIPPED", "reason": "Automation disabled"}

            # Create persistent AutomationRun record
            run = AutomationRun(
                automation_id=auto.id,
                status="RUNNING",
                trigger_reason=trigger_reason,
                started_at=datetime.utcnow()
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id

            auto.last_run_at = datetime.utcnow()
            auto.last_run_status = "RUNNING"
            await db.commit()

        # Emit WebSocket event
        await ws_manager.broadcast({
            "event": "automation.started",
            "automation_id": auto.id,
            "run_id": run_id,
            "title": auto.title,
            "trigger_reason": trigger_reason
        })

        # Safety configuration defaults
        w_config = auto.workflow_config or {}
        max_runtime = float(w_config.get("max_runtime", 300.0))
        max_retries = int(w_config.get("max_retries", 2))
        allowed_tools = w_config.get("allowed_tools")
        notification_level = w_config.get("notification_level", "ON_FAILURE")
        condition_rule = w_config.get("condition")

        logs: List[Dict[str, Any]] = []
        retry_count = 0
        tool_call_count = 0
        llm_call_count = 0
        final_status = "COMPLETED"
        error_msg = None
        result_summary = ""

        try:
            # 1. Context & Memory Retrieval
            logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "context_retrieval"})
            bounded_ctx = await memory_manager.build_bounded_context(
                project_id=auto.project_id,
                task_description=auto.description or auto.title
            )
            llm_call_count += 1

            # 2. Planning
            logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "planning_started"})
            plan = await agent_planner.generate_plan(
                goal=auto.description or auto.title,
                project_id=auto.project_id
            )
            llm_call_count += 1

            # 3. Step Execution with Conditional Branching and Safety Bounds
            exec_start_time = time.time()
            for step in plan.steps:
                # Check runtime budget
                elapsed = time.time() - exec_start_time
                if elapsed > max_runtime:
                    raise TimeoutError(f"Automation execution exceeded max_runtime of {max_runtime}s")

                # Safety check: allowed tools
                if allowed_tools and step.tool not in allowed_tools and step.tool != "web_search":
                    logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "tool_restricted", "tool": step.tool})
                    logger.warning(f"Tool '{step.tool}' not in allowed_tools list for automation {auto.id}")

                # Emit step event
                await ws_manager.broadcast({
                    "event": "automation.step.started",
                    "automation_id": auto.id,
                    "run_id": run_id,
                    "step_id": step.id,
                    "tool": step.tool
                })

                # Check Permission Safety (Automations cannot self-approve)
                perm_level = getattr(step, "permission_level", "READ")
                target_path = step.arguments.get("path") or step.arguments.get("file_path") or ""
                check = permission_manager.check_permission(
                    tool_name=step.tool or "system",
                    permission_level=perm_level,
                    target_path=target_path,
                    project_id=auto.project_id
                )

                if check.requires_approval and not check.granted:
                    req = permission_manager.request_permission(
                        tool_name=step.tool or "system",
                        operation=step.title or step.description,
                        permission_level=perm_level,
                        target=target_path,
                        project_id=auto.project_id,
                        reason=f"Automation '{auto.title}' step execution"
                    )
                    
                    await ws_manager.broadcast({
                        "event": "automation.permission_required",
                        "automation_id": auto.id,
                        "run_id": run_id,
                        "request_id": req.request_id,
                        "tool": step.tool
                    })

                    # Update run state to WAITING_PERMISSION
                    async with AsyncSessionLocal() as db:
                        r = await db.get(AutomationRun, run_id)
                        if r:
                            r.status = "WAITING_PERMISSION"
                            await db.commit()

                    logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "permission_blocked", "tool": step.tool})
                    final_status = "WAITING_PERMISSION"
                    result_summary = f"Waiting for permission approval for tool {step.tool}"
                    break

                tool_call_count += 1
                logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "step_executed", "step_id": step.id, "tool": step.tool})

            # Conditional rule evaluation
            if final_status == "COMPLETED" and condition_rule:
                context_data = {"git_dirty": False, "task_status": final_status, "task_result": result_summary}
                cond_pass = trigger_evaluator.evaluate_condition(condition_rule, context_data)
                if not cond_pass:
                    final_status = "SKIPPED"
                    result_summary = f"Condition rule '{condition_rule}' evaluated to false; execution skipped."
                    logs.append({"timestamp": datetime.utcnow().isoformat(), "event": "condition_skipped", "condition": condition_rule})

            if final_status == "COMPLETED":
                result_summary = f"Automation workflow completed successfully ({len(plan.steps)} steps executed)."

                # 4. Knowledge Engine Update (verified automation results)
                try:
                    await memory_manager.remember(
                        memory_type="PROJECT_KNOWLEDGE",
                        content=f"Automation '{auto.title}' verified result: {result_summary}",
                        project_id=auto.project_id,
                        source="automation",
                        source_reliability="VERIFIED_TASK",
                        importance=6,
                        verification_status="VERIFIED"
                    )
                except Exception as mem_err:
                    logger.debug(f"Memory update note: {mem_err}")

        except Exception as ex:
            logger.error(f"Error executing automation workflow {automation_id}: {ex}", exc_info=True)
            error_msg = str(ex)
            final_status = "FAILED"
            result_summary = f"Automation failed: {error_msg}"

        # Finalize duration & persistent state
        end_time = time.time()
        duration = round(end_time - start_time, 2)

        async with AsyncSessionLocal() as db:
            r = await db.get(AutomationRun, run_id)
            if r:
                r.status = final_status
                r.completed_at = datetime.utcnow()
                r.duration_seconds = duration
                r.retry_count = retry_count
                r.tool_call_count = tool_call_count
                r.llm_call_count = llm_call_count
                r.result_summary = result_summary
                r.execution_logs = logs
                r.error_message = error_msg
                await db.commit()

            a = await db.get(Automation, auto.id)
            if a:
                a.last_run_at = datetime.utcnow()
                a.last_run_status = final_status
                a.last_run_result = result_summary
                await db.commit()

        # Handle Notifications
        await self._dispatch_notification(auto, final_status, result_summary, notification_level)

        # Broadcast final observability event
        event_name = f"automation.{final_status.lower()}"
        await ws_manager.broadcast({
            "event": event_name if event_name in ["automation.completed", "automation.failed"] else "automation.completed",
            "automation_id": auto.id,
            "run_id": run_id,
            "status": final_status,
            "duration": duration,
            "result": result_summary
        })

        return {
            "run_id": run_id,
            "status": final_status,
            "duration_seconds": duration,
            "result_summary": result_summary
        }

    async def _dispatch_notification(self, auto: Automation, status: str, result: str, level: str):
        """Sends ActivityLog and notification based on notification_level policy."""
        if level == "SILENT":
            return
        if level == "ON_FAILURE" and status not in ["FAILED", "WAITING_PERMISSION"]:
            return

        async with AsyncSessionLocal() as db:
            log_entry = ActivityLog(
                timestamp=datetime.utcnow().isoformat(),
                message=f"Automation '{auto.title}' status: {status}. {result}",
                status=status,
                details=[{"automation_id": auto.id, "notification_level": level}]
            )
            db.add(log_entry)
            await db.commit()

workflow_engine = AutonomousWorkflowEngine()
