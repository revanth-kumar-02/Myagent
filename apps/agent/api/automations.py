from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.session import get_db
from db.models import Automation
from schemas.schemas import AutomationCreate, AutomationResponse

router = APIRouter(prefix="/automations", tags=["Automations"])

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
    return auto

@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(automation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Automation).where(Automation.id == automation_id))
    auto = result.scalar_one_or_none()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")
    return auto
