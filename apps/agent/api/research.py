import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.session import get_db
from db.models import ResearchSession
from schemas.schemas import ResearchSessionCreate, ResearchSessionResponse
from api.websocket import ws_manager

router = APIRouter(prefix="/research", tags=["Research"])

@router.get("", response_model=List[ResearchSessionResponse])
async def list_research_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ResearchSession))
    return result.scalars().all()

@router.post("", response_model=ResearchSessionResponse)
async def create_research_session(session_in: ResearchSessionCreate, db: AsyncSession = Depends(get_db)):
    code = f"{random.randint(100,999)}-RES-{session_in.title[:4].upper()}"
    session = ResearchSession(
        session_code=code,
        status="running",
        confidence=50,
        **session_in.model_dump()
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    await ws_manager.broadcast({
        "event": "research_started",
        "session_id": session.id,
        "title": session.title,
        "session_code": code
    })

    return session

@router.get("/{session_id}", response_model=ResearchSessionResponse)
async def get_research_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session
