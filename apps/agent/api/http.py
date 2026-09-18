"""
api.http — HTTP endpoints

REST is used only for:
  - Health check
  - File upload (multipart)
  - Project CRUD
  - Model registry info

All real-time communication uses WebSocket (/ws).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check — returns 200 if the server is running."""
    return HealthResponse(status="ok")


@router.get("/models")
async def list_models() -> dict:
    """Return the current model registry (names and capabilities only; no model IDs)."""
    raise NotImplementedError  # TODO: implement in feature phase


@router.post("/projects")
async def create_project() -> dict:
    """Create a new project record."""
    raise NotImplementedError  # TODO: implement in feature phase


@router.get("/projects")
async def list_projects() -> dict:
    """List all projects."""
    raise NotImplementedError  # TODO: implement in feature phase


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    """Delete a project and all its indexed data."""
    raise NotImplementedError  # TODO: implement in feature phase


@router.post("/projects/{project_id}/upload")
async def upload_file(project_id: str) -> dict:
    """Upload a file to a project for indexing."""
    raise NotImplementedError  # TODO: implement in feature phase
