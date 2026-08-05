from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.session import get_db
from db.models import SettingModel
from schemas.schemas import SettingUpdate, SettingResponse
from config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=List[SettingResponse])
async def list_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SettingModel))
    return result.scalars().all()

@router.post("", response_model=SettingResponse)
async def update_setting(setting_in: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SettingModel).where(SettingModel.key == setting_in.key))
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = setting_in.value
    else:
        setting = SettingModel(key=setting_in.key, value=setting_in.value)
        db.add(setting)
        
    await db.commit()
    await db.refresh(setting)

    # If setting is LLM provider / model, update runtime config
    if setting_in.key == "llm_provider":
        settings.LLM_PROVIDER = setting_in.value
    elif setting_in.key == "llm_model":
        settings.LLM_MODEL = setting_in.value
    elif setting_in.key == "llm_api_key":
        settings.LLM_API_KEY = setting_in.value

    return setting
