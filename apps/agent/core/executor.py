import asyncio
import re
from typing import Optional, Callable, Awaitable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from core.state import ExecutionContext, AgentState, StepExecutionState
from core.planner import TaskPlan
from core.tools.registry import tool_registry
from core.verifier import AgentVerifier
from api.websocket import ws_manager

class AgentExecutor:
    def __init__(self, verifier: Optional[AgentVerifier] = None):
        self.verifier = verifier or AgentVerifier()

    def _build_tool_params(self, tool_name: str, step: StepExecutionState, ctx: ExecutionContext) -> Dict[str, Any]:
        """Constructs valid structured parameter input dictionaries based on step and context."""
        text = f"{step.title} {step.description} {ctx.goal}"

        if tool_name == "list_directory":
            match = re.search(r'path[:\s]+(["\']?)([^"\';\s]+)\1', text, re.IGNORECASE)
            path = match.group(2) if match else "."
            return {"path": path, "limit": 100}

        elif tool_name == "search_files":
            match = re.search(r'(?:find|search|query)[:\s]+(["\']?)([^"\';\s]+)\1', text, re.IGNORECASE)
            query = match.group(2) if match else "auth"
            return {"query": query, "search_type": "filename", "root_path": "."}

        elif tool_name == "read_file":
            match = re.search(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            path = match.group(1) if match else "README.md"
            return {"path": path}

        elif tool_name == "inspect_file":
            match = re.search(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            path = match.group(1) if match else "README.md"
            return {"path": path}

        elif tool_name == "create_file":
            match = re.search(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            path = match.group(1) if match else "notes.md"
            content = f"# Notes for {ctx.goal}\nCreated autonomously by Cocoa Agent."
            return {"path": path, "content": content}

        elif tool_name == "edit_file":
            match = re.search(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            path = match.group(1) if match else "README.md"
            return {
                "path": path,
                "target_content": "# README",
                "replacement_content": f"# README\nUpdated autonomously for {ctx.goal}"
            }

        elif tool_name == "move_file":
            paths = re.findall(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            src = paths[0] if len(paths) > 0 else "notes.md"
            dest = paths[1] if len(paths) > 1 else "notes_archive.md"
            return {"source_path": src, "destination_path": dest}

        elif tool_name == "delete_file":
            match = re.search(r'([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', text)
            path = match.group(1) if match else "temp.txt"
            return {"path": path}

        return {"query": step.title, "goal": ctx.goal, "description": step.description}

    async def execute_plan(
        self,
        ctx: ExecutionContext,
        plan: TaskPlan,
        on_activity: Optional[Callable[[str, str, dict], Awaitable[None]]] = None
    ) -> ExecutionContext:
        ctx.current_state = AgentState.EXECUTING
        
        # Populate context steps from plan
        ctx.steps = [
            StepExecutionState(
                step_id=s.id,
                step_number=idx + 1,
                title=s.title,
                description=s.description,
                tool=s.tool,
                status=AgentState.IDLE
            )
            for idx, s in enumerate(plan.steps)
        ]

        if on_activity:
            await on_activity("plan.created", f"Plan created with {len(ctx.steps)} steps", {"steps_count": len(ctx.steps)})

        await ws_manager.broadcast({
            "event": "plan.created",
            "task_id": ctx.task_id,
            "status": "executing",
            "message": f"Generated {len(ctx.steps)} execution steps",
            "details": {"steps": [s.model_dump() for s in ctx.steps]}
        })

        for idx, step in enumerate(ctx.steps):
            ctx.current_step_index = idx
            step.status = AgentState.EXECUTING

            if on_activity:
                await on_activity("step.started", f"Starting Step {step.step_number}: {step.title}", {"step": step.model_dump()})

            await ws_manager.broadcast({
                "event": "step.started",
                "task_id": ctx.task_id,
                "status": "executing",
                "message": f"Step {step.step_number}: {step.title}",
                "details": step.model_dump()
            })

            # Execute tool
            tool_name = step.tool or "web_search"
            params = self._build_tool_params(tool_name, step, ctx)

            if on_activity:
                await on_activity("tool.started", f"Invoking tool '{tool_name}'", {"tool": tool_name, "params": params})

            await ws_manager.broadcast({
                "event": "tool.started",
                "task_id": ctx.task_id,
                "status": "executing",
                "message": f"Tool '{tool_name}' executing...",
                "details": {"tool": tool_name, "params": params}
            })

            tool_res = await tool_registry.execute_tool(tool_name, params)

            if tool_res.success:
                if on_activity:
                    await on_activity("tool.completed", f"Tool '{tool_name}' finished execution", {"success": True, "data": tool_res.data})

                await ws_manager.broadcast({
                    "event": "tool.completed",
                    "task_id": ctx.task_id,
                    "status": "executing",
                    "message": f"Tool '{tool_name}' completed",
                    "details": {"success": True, "output": tool_res.data}
                })
            else:
                if on_activity:
                    await on_activity("tool.failed", f"Tool '{tool_name}' failed: {tool_res.error}", {"success": False, "error": tool_res.error})

                await ws_manager.broadcast({
                    "event": "tool.failed",
                    "task_id": ctx.task_id,
                    "status": "failed",
                    "message": f"Tool '{tool_name}' failed",
                    "details": {"error": tool_res.error}
                })

            # Verification step
            ctx.current_state = AgentState.VERIFYING
            verification = await self.verifier.verify_step(ctx.goal, step.title, tool_res.data if tool_res.success else tool_res.error)

            if verification.success and tool_res.success:
                step.status = AgentState.COMPLETED
                step.result = str(tool_res.data)
                ctx.observations.append({"step_id": step.step_id, "title": step.title, "output": tool_res.data})

                if on_activity:
                    await on_activity("step.completed", f"Step {step.step_number} verified and completed", {"reason": verification.reason})

                await ws_manager.broadcast({
                    "event": "step.completed",
                    "task_id": ctx.task_id,
                    "status": "executing",
                    "message": f"Step {step.step_number} completed",
                    "details": {"reason": verification.reason}
                })
            else:
                fail_reason = verification.reason if not verification.success else str(tool_res.error)
                step.status = AgentState.FAILED
                step.error = fail_reason
                ctx.current_state = AgentState.FAILED
                ctx.error_message = f"Step {step.step_number} failed verification: {fail_reason}"

                if on_activity:
                    await on_activity("step.failed", f"Step {step.step_number} failed", {"reason": fail_reason})

                await ws_manager.broadcast({
                    "event": "step.failed",
                    "task_id": ctx.task_id,
                    "status": "failed",
                    "message": f"Step {step.step_number} failed",
                    "details": {"reason": fail_reason}
                })
                return ctx

        # Final Goal Verification
        final_ver = await self.verifier.verify_goal_completion(ctx.goal, ctx.observations)
        if final_ver.success:
            ctx.current_state = AgentState.COMPLETED
            ctx.final_result = f"Goal '{ctx.goal}' successfully completed and verified. Summary: {final_ver.reason}"

            if on_activity:
                await on_activity("agent.completed", "Goal verified and task completed", {"result": ctx.final_result})

            await ws_manager.broadcast({
                "event": "agent.completed",
                "task_id": ctx.task_id,
                "status": "completed",
                "message": "Task completed successfully",
                "result": ctx.final_result
            })
        else:
            ctx.current_state = AgentState.FAILED
            ctx.error_message = final_ver.reason

            if on_activity:
                await on_activity("agent.failed", "Final verification failed", {"reason": final_ver.reason})

            await ws_manager.broadcast({
                "event": "agent.failed",
                "task_id": ctx.task_id,
                "status": "failed",
                "message": "Task failed final verification",
                "error": final_ver.reason
            })

        return ctx
