from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict
from pydantic import BaseModel, Field

from db.session import get_db
from db.models import SettingModel
from schemas.schemas import SettingUpdate, SettingResponse
from config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])

class BulkSettingsUpdate(BaseModel):
    settings: Dict[str, str]

def mask_secret(key: str, val: str) -> str:
    """Masks secret settings for safe UI transmission."""
    if not val:
        return ""
    lower_key = key.lower()
    if "key" in lower_key or "secret" in lower_key or "password" in lower_key or "token" in lower_key:
        if len(val) <= 8:
            return "••••••••"
        return val[:5] + "••••••••" + val[-4:]
    return val

def update_runtime_settings(key: str, value: str):
    """Syncs updated setting to application runtime configuration."""
    k = key.lower()
    if k == "llm_provider":
        settings.LLM_PROVIDER = value
    elif k == "llm_model":
        settings.LLM_MODEL = value
    elif k == "llm_api_key":
        settings.LLM_API_KEY = value
    elif k == "tavily_api_key":
        settings.TAVILY_API_KEY = value

@router.get("", response_model=List[SettingResponse])
async def list_settings(mask_secrets: bool = False, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SettingModel))
    all_settings = result.scalars().all()
    
    if mask_secrets:
        return [
            SettingResponse(
                key=s.key,
                value=mask_secret(s.key, s.value),
                updated_at=s.updated_at
            )
            for s in all_settings
        ]
    return all_settings

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

    update_runtime_settings(setting.key, setting.value)
    return setting

@router.post("/bulk", response_model=List[SettingResponse])
async def update_settings_bulk(payload: BulkSettingsUpdate, db: AsyncSession = Depends(get_db)):
    updated_items = []
    for key, val in payload.settings.items():
        result = await db.execute(select(SettingModel).where(SettingModel.key == key))
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = str(val)
        else:
            setting = SettingModel(key=key, value=str(val))
            db.add(setting)
        
        update_runtime_settings(key, str(val))
        updated_items.append(setting)

    await db.commit()
    for s in updated_items:
        await db.refresh(s)

    return updated_items
