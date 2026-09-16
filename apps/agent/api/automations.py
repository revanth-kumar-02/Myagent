from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from db.session import get_db
from db.models import Automation, AutomationRun
from schemas.schemas import AutomationCreate, AutomationResponse
from core.scheduler_manager import automation_scheduler
from core.automations.nl_parser import nl_automation_parser
from api.websocket import ws_manager

router = APIRouter(prefix="/automations", tags=["Automations"])

class AutomationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    workflow_config: Optional[dict] = None
    is_active: Optional[bool] = None
    project_id: Optional[str] = None

class NLParseRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None

class AutomationRunResponse(BaseModel):
    id: str
    automation_id: str
    status: str
    trigger_reason: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    result_summary: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[AutomationResponse])
async def list_automations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation))
    return result.scalars().all()

@router.post("", response_model=AutomationResponse)
async def create_automation(auto_in: AutomationCreate, db: AsyncSession = Depends(get_db)):
    auto = Automation(**auto_in.model_dump())
    db.add(auto)
    await db.commit()
    await db.refresh(auto)
    
    if auto.is_active:
        automation_scheduler.register_automation_job(auto)
        await ws_manager.broadcast({
            "event": "automation.enabled",
            "automation_id": auto.id,
            "title": auto.title
        })

    return auto

@router.post("/parse-nl")
async def parse_natural_language_automation(req: NLParseRequest):
    parsed = await nl_automation_parser.parse_natural_language(req.prompt, req.project_id)
    return {"status": "SUCCESS", "definition": parsed}

@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")
    return auto

@router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation(automation_id: str, auto_in: AutomationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    update_data = auto_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(auto, field, val)

    await db.commit()
    await db.refresh(auto)

    if auto.is_active:
        automation_scheduler.register_automation_job(auto)
        await ws_manager.broadcast({
            "event": "automation.enabled",
            "automation_id": auto.id,
            "title": auto.title
        })
    else:
        automation_scheduler.remove_automation_job(auto.id)
        await ws_manager.broadcast({
            "event": "automation.disabled",
            "automation_id": auto.id,
            "title": auto.title
        })

    return auto

@router.post("/{automation_id}/enable", response_model=AutomationResponse)
async def enable_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    auto.is_active = True
    await db.commit()
    await db.refresh(auto)
    automation_scheduler.register_automation_job(auto)

    await ws_manager.broadcast({
        "event": "automation.enabled",
        "automation_id": auto.id,
        "title": auto.title
    })
    return auto

@router.post("/{automation_id}/disable", response_model=AutomationResponse)
async def disable_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    auto.is_active = False
    await db.commit()
    await db.refresh(auto)
    automation_scheduler.remove_automation_job(auto.id)

    await ws_manager.broadcast({
        "event": "automation.disabled",
        "automation_id": auto.id,
        "title": auto.title
    })
    return auto

@router.post("/{automation_id}/run")
async def run_automation_now(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    await automation_scheduler.trigger_now(auto.id)
    return {"message": f"Automation '{auto.title}' triggered", "automation_id": auto.id}

@router.post("/{automation_id}/trigger")
async def trigger_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    return await run_automation_now(automation_id, db)

@router.post("/{automation_id}/toggle", response_model=AutomationResponse)
async def toggle_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    if auto.is_active:
        return await disable_automation(automation_id, db)
    else:
        return await enable_automation(automation_id, db)

@router.get("/{automation_id}/runs")
async def get_automation_runs(automation_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AutomationRun)
        .where(AutomationRun.automation_id == automation_id)
        .order_by(AutomationRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "automation_id": r.automation_id,
            "status": r.status,
            "trigger_reason": r.trigger_reason,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_seconds": r.duration_seconds,
            "retry_count": r.retry_count,
            "tool_call_count": r.tool_call_count,
            "llm_call_count": r.llm_call_count,
            "result_summary": r.result_summary,
            "error_message": r.error_message,
            "execution_logs": r.execution_logs
        }
        for r in runs
    ]

@router.delete("/{automation_id}")
async def delete_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    automation_scheduler.remove_automation_job(auto.id)
    await db.delete(auto)
    await db.commit()
    return {"message": "Automation deleted", "automation_id": automation_id}
