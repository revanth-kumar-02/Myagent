"""
api.http — HTTP endpoints for Kora Agent

REST is used for:
  - Health checks & system status
  - Model registry information (capabilities & metadata; no secrets)
  - Project management (CRUD)
  - Memory exploration & management
  - External DuckDuckGo research queries
  - Background task queries
  - Observability & Activity feeds
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_model_registry, get_research_router
from models.registry import ModelRegistry
from research.router import ResearchRouter

router = APIRouter(prefix="/api")

# In-memory stores for runtime desktop state when Postgres is local/standalone
_projects_store: dict[str, dict[str, Any]] = {
    "default-project": {
        "id": "default-project",
        "name": "Kora Workspace",
        "description": "Primary development and research workspace",
        "root_path": "/workspace",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 42,
        "chunk_count": 128,
    }
}

_memory_store: list[dict[str, Any]] = [
    {
        "id": "mem-1",
        "content": "Prefers Python for backend services and Flutter/Dart for desktop user interfaces.",
        "type": "preference",
        "confidence": 0.95,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": "default-project",
    },
    {
        "id": "mem-2",
        "content": "Active research topic: Autonomous agent multi-modal reasoning with Qwen3 and Gemma-4.",
        "type": "fact",
        "confidence": 0.90,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": "default-project",
    }
]

_tasks_store: list[dict[str, Any]] = [
    {
        "id": "task-101",
        "title": "Index Workspace Codebase",
        "status": "completed",
        "category": "RAG",
        "duration_ms": 1240,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": "default-project",
    },
    {
        "id": "task-102",
        "title": "Autonomous Decision Loop Monitoring",
        "status": "running",
        "category": "Agent Core",
        "duration_ms": 530,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": "default-project",
    }
]

_activity_store: list[dict[str, Any]] = [
    {
        "id": "act-1",
        "event_type": "MODEL_ROUTE",
        "details": "Routed capability 'chat' to model 'qwen-chat'",
        "latency_ms": 12,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "act-2",
        "event_type": "RAG_RETRIEVE",
        "details": "Dense vector retrieval completed with BAAI/bge-m3",
        "latency_ms": 48,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
]


# ── Schemas ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    models_available: int = 0


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""
    root_path: str = ""


class MemoryCreateRequest(BaseModel):
    content: str
    type: str = "fact"
    confidence: float = 1.0
    project_id: str | None = None


class ResearchRequest(BaseModel):
    query: str
    max_results: int = 5


# ── Health ──────────────────────────────────────────────────────────────────

_start_time = time.time()

@router.get("/health", response_model=HealthResponse)
async def health(registry: ModelRegistry = Depends(get_model_registry)) -> HealthResponse:
    """Liveness & readiness check."""
    num_models = len(list(registry.all()))
    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        models_available=num_models,
    )


# ── Model Registry ──────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(registry: ModelRegistry = Depends(get_model_registry)) -> dict[str, Any]:
    """
    Return all registered models and their capabilities.
    Strictly excludes all API tokens or sensitive headers.
    """
    models_data = []
    for cfg in registry.all():
        models_data.append({
            "name": cfg.name,
            "provider": cfg.provider,
            "capabilities": cfg.capabilities,
            "context_window": cfg.context_window,
            "dimension": cfg.dimension,
        })
    return {"models": models_data}


# ── Projects ────────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects() -> dict[str, Any]:
    """List all workspace projects."""
    return {"projects": list(_projects_store.values())}


@router.post("/projects")
async def create_project(req: ProjectCreateRequest) -> dict[str, Any]:
    """Create a new project."""
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": req.name,
        "description": req.description,
        "root_path": req.root_path or f"/workspace/{req.name.lower().replace(' ', '_')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 0,
        "chunk_count": 0,
    }
    _projects_store[project_id] = project
    return project


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    """Get project details."""
    if project_id not in _projects_store:
        raise HTTPException(status_code=404, detail="Project not found")
    return _projects_store[project_id]


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    """Delete a project."""
    if project_id in _projects_store:
        del _projects_store[project_id]
        return {"deleted": True, "project_id": project_id}
    raise HTTPException(status_code=404, detail="Project not found")


# ── Tasks ───────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks() -> dict[str, Any]:
    """List running and historical agent tasks."""
    return {"tasks": _tasks_store}


# ── Memory ──────────────────────────────────────────────────────────────────

@router.get("/memory")
async def list_memories(project_id: str | None = None) -> dict[str, Any]:
    """List stored memories, optionally filtered by project."""
    if project_id:
        filtered = [m for m in _memory_store if m.get("project_id") == project_id]
        return {"memories": filtered}
    return {"memories": _memory_store}


@router.post("/memory")
async def create_memory(req: MemoryCreateRequest) -> dict[str, Any]:
    """Store a new memory item."""
    mem_id = f"mem-{uuid.uuid4().hex[:8]}"
    item = {
        "id": mem_id,
        "content": req.content,
        "type": req.type,
        "confidence": req.confidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": req.project_id or "default-project",
    }
    _memory_store.insert(0, item)
    return item


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete a memory entry."""
    global _memory_store
    _memory_store = [m for m in _memory_store if m["id"] != memory_id]
    return {"deleted": True, "memory_id": memory_id}


# ── Research ────────────────────────────────────────────────────────────────

@router.post("/research")
async def perform_research(
    req: ResearchRequest,
    research_router: ResearchRouter = Depends(get_research_router),
) -> dict[str, Any]:
    """
    Execute DuckDuckGo live search and return normalized results.
    """
    try:
        res = await research_router.search(query=req.query, max_results=req.max_results)
        results = []
        for r in getattr(res, "results", []):
            results.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "score": getattr(r, "score", 1.0),
            })
        return {
            "query": req.query,
            "results": results,
            "count": len(results),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research search failed: {exc}")


# ── Activity & Observability ────────────────────────────────────────────────

@router.get("/activity")
async def list_activity() -> dict[str, Any]:
    """List recent agent activity and execution logs."""
    return {"activity": _activity_store}
