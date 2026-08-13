import asyncio
from typing import Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from core.state import ExecutionContext, AgentState, StepExecutionState
from core.planner import TaskPlan
from core.tools.registry import tool_registry
from core.verifier import AgentVerifier
from api.websocket import ws_manager

class AgentExecutor:
    def __init__(self, verifier: Optional[AgentVerifier] = None):
        self.verifier = verifier or AgentVerifier()

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
            params = {"query": step.title, "goal": ctx.goal, "description": step.description}

            if on_activity:
                await on_activity("tool.started", f"Invoking tool '{tool_name}'", {"tool": tool_name, "params": params})

            await ws_manager.broadcast({
                "event": "tool.started",
                "task_id": ctx.task_id,
                "status": "executing",
                "message": f"Tool '{tool_name}' executing...",
                "details": {"tool": tool_name}
            })

            tool_res = await tool_registry.execute_tool(tool_name, params)

            if on_activity:
                await on_activity("tool.completed", f"Tool '{tool_name}' finished execution", {"success": tool_res.success, "data": tool_res.data})

            await ws_manager.broadcast({
                "event": "tool.completed",
                "task_id": ctx.task_id,
                "status": "executing",
                "message": f"Tool '{tool_name}' completed",
                "details": {"success": tool_res.success, "output": tool_res.data}
            })

            # Verification step
            ctx.current_state = AgentState.VERIFYING
            verification = await self.verifier.verify_step(ctx.goal, step.title, tool_res.data)

            if verification.success:
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
                step.status = AgentState.FAILED
                step.error = verification.reason
                ctx.current_state = AgentState.FAILED
                ctx.error_message = f"Step {step.step_number} failed verification: {verification.reason}"

                if on_activity:
                    await on_activity("step.failed", f"Step {step.step_number} failed", {"reason": verification.reason})

                await ws_manager.broadcast({
                    "event": "step.failed",
                    "task_id": ctx.task_id,
                    "status": "failed",
                    "message": f"Step {step.step_number} failed",
                    "details": {"reason": verification.reason}
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
