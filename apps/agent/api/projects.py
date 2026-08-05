from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.session import get_db
from db.models import Project
from schemas.schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project))
    return result.scalars().all()

@router.post("", response_model=ProjectResponse)
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(**project_in.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
