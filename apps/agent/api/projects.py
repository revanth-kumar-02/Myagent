import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from pydantic import BaseModel, Field

from db.session import get_db
from db.models import Project, Workspace
from schemas.schemas import ProjectResponse, WorkspaceResponse, ScanWorkspaceResponse
from core.workspace_scanner import WorkspaceScanner

router = APIRouter(prefix="/projects", tags=["Projects"])

class SetWorkspaceRequest(BaseModel):
    path: str = Field(..., description="Absolute filesystem path to root workspace directory")

@router.get("/workspace", response_model=Optional[WorkspaceResponse])
async def get_active_workspace(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace).where(Workspace.is_active == True))
    ws = result.scalar_one_or_none()
    if not ws:
        # Default workspace fallback if none active
        default_path = os.path.expanduser("~/Personal Space/Projects")
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Projects")
        if not os.path.exists(default_path):
            default_path = os.getcwd()
        
        ws = Workspace(name=os.path.basename(default_path) or "Default Workspace", path=default_path, is_active=True)
        db.add(ws)
        await db.commit()
        await db.refresh(ws)
    return ws

@router.post("/workspace", response_model=ScanWorkspaceResponse)
async def set_active_workspace(req: SetWorkspaceRequest, db: AsyncSession = Depends(get_db)):
    raw_path = req.path.strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Workspace directory path cannot be empty.")

    clean_path = os.path.abspath(os.path.expanduser(raw_path))
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=404, detail="Workspace directory does not exist.")

    if not os.path.isdir(clean_path):
        raise HTTPException(status_code=400, detail="Path is not a directory.")

    if not os.access(clean_path, os.R_OK):
        raise HTTPException(status_code=403, detail="Unable to access this directory.")

    # Deactivate existing workspaces
    res = await db.execute(select(Workspace))
    for existing in res.scalars().all():
        existing.is_active = False

    # Find or create workspace
    res = await db.execute(select(Workspace).where(Workspace.path == clean_path))
    ws = res.scalar_one_or_none()

    if not ws:
        ws = Workspace(name=os.path.basename(clean_path) or "Workspace", path=clean_path, is_active=True)
        db.add(ws)
    else:
        ws.is_active = True

    await db.commit()
    await db.refresh(ws)

    # Perform scan
    projects = await scan_workspace_internal(ws.id, ws.path, db)
    return ScanWorkspaceResponse(workspace=ws, projects=projects)

@router.post("/scan", response_model=ScanWorkspaceResponse)
async def rescan_projects(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Workspace).where(Workspace.is_active == True))
    ws = res.scalar_one_or_none()
    if not ws:
        ws = await get_active_workspace(db)

    projects = await scan_workspace_internal(ws.id, ws.path, db)
    return ScanWorkspaceResponse(workspace=ws, projects=projects)

async def scan_workspace_internal(ws_id: str, ws_path: str, db: AsyncSession) -> List[Project]:
    try:
        discovered = WorkspaceScanner.scan_directory(ws_path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail="Unable to access this directory.")

    # Fetch existing DB projects for workspace
    res = await db.execute(select(Project).where(Project.workspace_id == ws_id))
    existing_projects = res.scalars().all()
    existing_by_path = {p.path: p for p in existing_projects}

    discovered_paths = set()
    updated_projects = []

    for item in discovered:
        p_path = item["path"]
        discovered_paths.add(p_path)
        if p_path in existing_by_path:
            p = existing_by_path[p_path]
            p.title = item["title"]
            p.languages = item["languages"]
            p.frameworks = item["frameworks"]
            p.git_repository = item["git_repository"]
            p.detection_confidence = item.get("detection_confidence", "high")
            p.last_scanned = item["last_scanned"]
            p.last_modified = item["last_modified"]
            p.metadata_info = item["metadata_info"]
        else:
            p = Project(
                workspace_id=ws_id,
                title=item["title"],
                path=item["path"],
                description=item["description"],
                languages=item["languages"],
                frameworks=item["frameworks"],
                git_repository=item["git_repository"],
                detection_confidence=item.get("detection_confidence", "high"),
                last_scanned=item["last_scanned"],
                last_modified=item["last_modified"],
                metadata_info=item["metadata_info"]
            )
            db.add(p)
        updated_projects.append(p)

    # Remove projects that no longer exist in filesystem
    for p in existing_projects:
        if p.path not in discovered_paths:
            await db.delete(p)

    await db.commit()
    
    # Re-query updated list
    res_updated = await db.execute(select(Project).where(Project.workspace_id == ws_id))
    return res_updated.scalars().all()

@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    ws = await get_active_workspace(db)
    res = await db.execute(select(Project).where(Project.workspace_id == ws.id))
    projects = res.scalars().all()

    # Auto-scan if no projects exist in active workspace
    if not projects and os.path.exists(ws.path):
        projects = await scan_workspace_internal(ws.id, ws.path, db)

    return projects

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Project).where(Project.id == project_id))
    proj = res.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj
