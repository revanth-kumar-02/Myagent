from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from db.session import get_db
from db.models import Task, TaskStep, ActivityLog
from schemas.schemas import TaskCreate, TaskResponse, ActivityLogCreate, ActivityLogResponse
from api.websocket import ws_manager
from datetime import datetime

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.get("", response_model=List[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task).options(selectinload(Task.steps), selectinload(Task.activity_logs))
    )
    return result.scalars().all()

@router.post("", response_model=TaskResponse)
async def create_task(task_in: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(**task_in.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Broadcast task creation via WebSocket
    await ws_manager.broadcast({
        "event": "task_created",
        "task_id": task.id,
        "title": task.title,
    })

    return task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.steps), selectinload(Task.activity_logs))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/activity", response_model=ActivityLogResponse)
async def add_activity_log(task_id: str, activity_in: ActivityLogCreate, db: AsyncSession = Depends(get_db)):
    log = ActivityLog(task_id=task_id, **activity_in.model_dump(exclude={"task_id"}))
    db.add(log)
    await db.commit()
    await db.refresh(log)

    await ws_manager.broadcast({
        "event": "activity_logged",
        "task_id": task_id,
        "timestamp": log.timestamp,
        "message": log.message,
        "status": log.status,
        "details": log.details,
    })

    return log
