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

from api.deps import get_model_registry, get_research_router, get_tool_registry
from models.registry import ModelRegistry
from research.router import ResearchRouter
from tools.registry import ToolRegistry

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

_memory_store: list[dict[str, Any]] = []

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
    type: str = "user_preference"
    confidence: float = 1.0
    importance: float = 0.5
    project_id: str | None = None
    source: str = "user_explicit"


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    type: str | None = None
    confidence: float | None = None
    importance: float | None = None
    status: str | None = None


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
async def list_memories(
    project_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List stored memories, optionally filtered by project, type, or status."""
    res = list(_memory_store)
    if project_id:
        res = [m for m in res if m.get("project_id") == project_id or m.get("project_id") is None]
    if type:
        res = [m for m in res if m.get("type") == type]
    if status:
        res = [m for m in res if m.get("status") == status]
    return {"memories": res}


@router.post("/memory")
async def create_memory(req: MemoryCreateRequest) -> dict[str, Any]:
    """Store a new memory item."""
    mem_id = f"mem-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    meta: dict[str, Any] = {}
    item: dict[str, Any] = {
        "id": mem_id,
        "content": req.content,
        "type": req.type,
        "confidence": req.confidence,
        "importance": req.importance,
        "source": req.source,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "project_id": req.project_id or "default-project",
        "metadata": meta,
    }
    _memory_store.insert(0, item)
    return item


@router.patch("/memory/{memory_id}")
@router.put("/memory/{memory_id}")
async def update_memory(memory_id: str, req: MemoryUpdateRequest) -> dict[str, Any]:
    """Correct or update an existing memory item."""
    now = datetime.now(timezone.utc).isoformat()
    for m in _memory_store:
        if m["id"] == memory_id:
            if req.content is not None:
                m["content"] = req.content
            if req.type is not None:
                m["type"] = req.type
            if req.confidence is not None:
                m["confidence"] = req.confidence
            if req.importance is not None:
                m["importance"] = req.importance
            if req.status is not None:
                m["status"] = req.status
            m["updated_at"] = now
            return m
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.post("/memory/{memory_id}/toggle")
async def toggle_memory(memory_id: str) -> dict[str, Any]:
    """Toggle memory between active and archived."""
    now = datetime.now(timezone.utc).isoformat()
    for m in _memory_store:
        if m["id"] == memory_id:
            m["status"] = "archived" if m.get("status") == "active" else "active"
            m["updated_at"] = now
            return m
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete/forget a memory entry permanently."""
    global _memory_store
    _memory_store = [m for m in _memory_store if m["id"] != memory_id]
    return {"deleted": True, "memory_id": memory_id}


@router.get("/memory/graph")
@router.get("/graph")
async def get_knowledge_graph(project_id: str | None = None) -> dict[str, Any]:
    """Return entities and relationships connected to memories and knowledge."""
    # Synthesize entities and relationships from active memories
    entities: list[dict[str, Any]] = [
        {"id": "ent-user", "name": "User", "type": "person", "label": "User"},
        {"id": "ent-kora", "name": "Kora", "type": "agent", "label": "Kora Agent"},
    ]
    relationships: list[dict[str, Any]] = []

    for m in _memory_store:
        if m.get("status") == "archived":
            continue
        mem_id = m["id"]
        mem_type = m.get("type", "fact")
        content = m.get("content", "")
        # Extract keywords as entities
        words = [w.strip(",.!?\"'") for w in content.split() if len(w) > 4 and w.lower() not in {"prefer", "always", "decided", "using", "project", "building"}]
        for w in words[:2]:
            ent_id = f"ent-{w.lower()}"
            if not any(e["id"] == ent_id for e in entities):
                entities.append({
                    "id": ent_id,
                    "name": w,
                    "type": "concept" if mem_type == "decision" else "technology",
                    "label": w,
                })
            relationships.append({
                "source": "User",
                "target": w,
                "type": "prefers" if "pref" in mem_type else ("decided" if "dec" in mem_type else "associated_with"),
                "confidence": m.get("confidence", 0.9),
                "memory_id": mem_id,
            })

    return {
        "entities": entities,
        "relationships": relationships,
        "entity_count": len(entities),
        "relationship_count": len(relationships),
    }


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


# ── Tools & Commands ────────────────────────────────────────────────────────
@router.get("/tools")
async def list_tools(tool_registry: ToolRegistry = Depends(get_tool_registry)) -> dict[str, Any]:
    """
    Return all registered agent tools and slash commands dynamically from ToolRegistry.
    """
    tools_data = [
        {
            "name": "search",
            "title": "/search",
            "description": "Query DuckDuckGo for live external evidence & docs",
            "category": "research",
            "icon": "travel_explore_rounded",
        },
        {
            "name": "research",
            "title": "/research",
            "description": "Deep multi-source web research & evidence synthesis",
            "category": "research",
            "icon": "bolt_rounded",
        },
        {
            "name": "rag",
            "title": "/rag",
            "description": "Query indexed local workspace files & code chunks",
            "category": "rag",
            "icon": "folder_open_rounded",
        },
    ]

    for tool in tool_registry.all():
        tools_data.append({
            "name": tool.tool_id or tool.name,
            "title": f"/{tool.tool_id or tool.name}",
            "description": tool.description,
            "category": tool.category.value if hasattr(tool.category, "value") else str(tool.category),
            "icon": "build_circle_rounded",
        })

    return {"tools": tools_data}


# ── Activity & Observability ────────────────────────────────────────────────

@router.get("/activity")
async def list_activity() -> dict[str, Any]:
    """List recent agent activity and execution logs."""
    return {"activity": _activity_store}
