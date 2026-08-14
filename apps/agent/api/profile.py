import getpass
import os
import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from db.session import get_db
from db.models import SettingModel

router = APIRouter(prefix="/profile", tags=["Profile"])

class ProfileResponse(BaseModel):
    username: str

class ProfileUpdate(BaseModel):
    username: str

def get_default_os_username() -> str:
    try:
        raw_user = getpass.getuser() or os.environ.get("USER") or os.environ.get("USERNAME") or "User"
    except Exception:
        raw_user = os.environ.get("USER") or os.environ.get("USERNAME") or "User"
    
    clean = raw_user.strip()
    if not clean:
        return "User"
    # Capitalize nicely if it's all lowercase (e.g. 'rev' -> 'Rev')
    if clean.islower():
        return clean.capitalize()
    return clean

@router.get("", response_model=ProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SettingModel).where(SettingModel.key == "user_profile"))
    setting = result.scalar_one_or_none()
    
    if setting and setting.value:
        try:
            data = json.loads(setting.value)
            if isinstance(data, dict) and data.get("username"):
                return ProfileResponse(username=data["username"])
        except Exception:
            if setting.value.strip():
                return ProfileResponse(username=setting.value.strip())

    # Fallback to default OS username
    default_name = get_default_os_username()
    return ProfileResponse(username=default_name)

@router.put("", response_model=ProfileResponse)
async def update_profile(profile_in: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SettingModel).where(SettingModel.key == "user_profile"))
    setting = result.scalar_one_or_none()
    
    payload = json.dumps({"username": profile_in.username.strip()})
    
    if setting:
        setting.value = payload
    else:
        setting = SettingModel(key="user_profile", value=payload)
        db.add(setting)
        
    await db.commit()
    return ProfileResponse(username=profile_in.username.strip())
