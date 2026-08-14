from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import Automation
from schemas.schemas import AutomationCreate, AutomationResponse
from core.scheduler_manager import automation_scheduler
from api.websocket import ws_manager

router = APIRouter(prefix="/automations", tags=["Automations"])

class AutomationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    is_active: Optional[bool] = None
    project_id: Optional[str] = None

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

@router.post("/{automation_id}/toggle", response_model=AutomationResponse)
async def toggle_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    auto.is_active = not auto.is_active
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

@router.post("/{automation_id}/trigger")
async def trigger_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    await automation_scheduler.trigger_now(auto.id)
    return {"message": f"Automation '{auto.title}' triggered", "automation_id": auto.id}

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
