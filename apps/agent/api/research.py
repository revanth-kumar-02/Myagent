import uuid
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from db.session import get_db
from db.models import ResearchSession, ResearchSource, ResearchFinding, ResearchEvidence
from schemas.schemas import (
    ResearchRunRequest,
    ResearchSessionResponse,
    ResearchSourceResponse,
    ResearchFindingResponse
)
from core.research.orchestrator import ResearchOrchestrator

router = APIRouter(prefix="/research", tags=["Research"])
orchestrator = ResearchOrchestrator()

@router.post("/run", response_model=ResearchSessionResponse)
async def run_research(
    req: ResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    query_text = req.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Research query cannot be empty.")

    session_code = f"RES-{uuid.uuid4().hex[:6].upper()}"
    title = f"Research: {query_text[:40]}"

    db_session = ResearchSession(
        session_code=session_code,
        title=title,
        brief=query_text,
        status="idle",
        confidence=95,
        project_id=req.project_id
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)

    # Trigger research execution in background task
    background_tasks.add_task(
        orchestrator.execute_research,
        session_id=db_session.id,
        query=query_text,
        project_id=req.project_id
    )

    # Re-query with loaded relationships for response schema
    res = await db.execute(
        select(ResearchSession)
        .options(
            selectinload(ResearchSession.sources),
            selectinload(ResearchSession.evidence),
            selectinload(ResearchSession.findings)
        )
        .where(ResearchSession.id == db_session.id)
    )
    full_session = res.scalar_one()

    # Dynamic map of query property
    response_data = ResearchSessionResponse.model_validate(full_session)
    response_data.query = full_session.brief
    return response_data

@router.get("", response_model=List[ResearchSessionResponse])
async def list_research_sessions(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ResearchSession)
        .options(
            selectinload(ResearchSession.sources),
            selectinload(ResearchSession.evidence),
            selectinload(ResearchSession.findings)
        )
        .order_by(ResearchSession.created_at.desc())
    )
    sessions = res.scalars().all()
    results = []
    for s in sessions:
        r = ResearchSessionResponse.model_validate(s)
        r.query = s.brief
        results.append(r)
    return results

@router.get("/{session_id}", response_model=ResearchSessionResponse)
async def get_research_session(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ResearchSession)
        .options(
            selectinload(ResearchSession.sources),
            selectinload(ResearchSession.evidence),
            selectinload(ResearchSession.findings)
        )
        .where(ResearchSession.id == session_id)
    )
    session_obj = res.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Research session not found.")

    r = ResearchSessionResponse.model_validate(session_obj)
    r.query = session_obj.brief
    return r

@router.get("/{session_id}/sources", response_model=List[ResearchSourceResponse])
async def get_research_sources(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ResearchSource).where(ResearchSource.research_session_id == session_id)
    )
    return res.scalars().all()

@router.get("/{session_id}/findings", response_model=List[ResearchFindingResponse])
async def get_research_findings(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ResearchFinding).where(ResearchFinding.research_session_id == session_id)
    )
    return res.scalars().all()

@router.post("/{session_id}/cancel", response_model=ResearchSessionResponse)
async def cancel_research_session(session_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ResearchSession)
        .options(
            selectinload(ResearchSession.sources),
            selectinload(ResearchSession.evidence),
            selectinload(ResearchSession.findings)
        )
        .where(ResearchSession.id == session_id)
    )
    session_obj = res.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Research session not found.")

    orchestrator.cancel_session(session_id)
    session_obj.status = "cancelled"
    await db.commit()
    await db.refresh(session_obj)

    r = ResearchSessionResponse.model_validate(session_obj)
    r.query = session_obj.brief
    return r
