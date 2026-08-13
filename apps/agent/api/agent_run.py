import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from db.models import Task
from schemas.schemas import TaskResponse
from core.agent import agent_orchestrator
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(tags=["Agent Run"])

class AgentRunRequest(BaseModel):
    goal: str = Field(description="Natural language goal statement for the agent")
    project_id: Optional[str] = Field(default=None, description="Optional associated project ID")

class AgentRunResponse(BaseModel):
    task: TaskResponse
    message: str

@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent_goal(
    req: AgentRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal statement cannot be empty")

    task_id = str(uuid.uuid4())
    
    # Create initial Task record in DB
    new_task = Task(
        id=task_id,
        title=req.goal,
        description=f"User Goal: {req.goal}",
        status="planning",
        project_id=req.project_id
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # Trigger Agent Core execution in background task
    background_tasks.add_task(agent_orchestrator.run_goal, req.goal, req.project_id, task_id)

    return AgentRunResponse(
        task=TaskResponse.model_validate(new_task),
        message=f"Agent execution initiated for task '{task_id}'"
    )
