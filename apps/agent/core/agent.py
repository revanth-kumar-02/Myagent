import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from db.models import Task, TaskStep, ActivityLog
from core.state import ExecutionContext, AgentState
from core.planner import AgentPlanner
from core.executor import AgentExecutor
from core.verifier import AgentVerifier
from api.websocket import ws_manager

class AgentOrchestrator:
    def __init__(
        self,
        planner: Optional[AgentPlanner] = None,
        executor: Optional[AgentExecutor] = None,
        verifier: Optional[AgentVerifier] = None
    ):
        self.planner = planner or AgentPlanner()
        self.verifier = verifier or AgentVerifier()
        self.executor = executor or AgentExecutor(verifier=self.verifier)

    async def run_goal(self, goal: str, project_id: Optional[str] = None, task_id: Optional[str] = None) -> Task:
        t_id = task_id or str(uuid.uuid4())
        
        async with AsyncSessionLocal() as db:
            # Check or create DB task
            task = await db.get(Task, t_id)
            if not task:
                task = Task(
                    id=t_id,
                    title=goal,
                    description=f"Goal: {goal}",
                    status="planning",
                    project_id=project_id
                )
                db.add(task)
                await db.commit()
                await db.refresh(task)

            # Broadcast starting event
            await ws_manager.broadcast({
                "event": "agent.started",
                "task_id": t_id,
                "status": "planning",
                "message": f"Starting autonomous goal planning for '{goal}'"
            })

            # Create Execution Context
            ctx = ExecutionContext(task_id=t_id, goal=goal, project_id=project_id, current_state=AgentState.PLANNING)

            # Helper for DB activity log insertion
            async def log_activity(event_type: str, message: str, details: dict):
                async with AsyncSessionLocal() as log_db:
                    now_str = datetime.now().strftime("%H:%M:%S")
                    log_entry = ActivityLog(
                        id=str(uuid.uuid4()),
                        task_id=t_id,
                        timestamp=now_str,
                        message=message,
                        status="active" if "start" in event_type else "done",
                        details=[str(v) for v in details.values()] if details else None
                    )
                    log_db.add(log_entry)
                    await log_db.commit()

            await log_activity("agent.started", f"Goal execution initialized: '{goal}'", {})

            # Generate Plan
            plan = await self.planner.generate_plan(goal)

            # Insert Plan Steps into DB
            for idx, s in enumerate(plan.steps):
                step_record = TaskStep(
                    id=str(uuid.uuid4()),
                    task_id=t_id,
                    step_number=idx + 1,
                    label=s.title,
                    status="pending"
                )
                db.add(step_record)
            
            task.status = "executing"
            await db.commit()

            # Execute Plan
            final_ctx = await self.executor.execute_plan(ctx, plan, on_activity=log_activity)

            # Update DB Task Status & Result
            task.status = final_ctx.current_state.value
            if final_ctx.final_result:
                task.result = final_ctx.final_result
            
            await db.commit()
            await db.refresh(task)
            return task

agent_orchestrator = AgentOrchestrator()
