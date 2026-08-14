from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.memory import memory_manager

router = APIRouter(prefix="/memories", tags=["memories"])

class MemoryCreateSchema(BaseModel):
    memory_type: str = Field(description="PROJECT | RESEARCH | USER_PREFERENCE")
    content: str = Field(description="Memory text content")
    project_id: Optional[str] = Field(default=None, description="Associated project ID")
    session_id: Optional[str] = Field(default=None, description="Associated session ID")
    source: str = Field(default="user", description="Source of memory")
    importance: int = Field(default=5, ge=1, le=10)
    has_evidence: bool = Field(default=True, description="Evidence flag for research memories")

class MemoryUpdateSchema(BaseModel):
    content: Optional[str] = Field(default=None)
    importance: Optional[int] = Field(default=None, ge=1, le=10)

class MemoryResponseSchema(BaseModel):
    id: str
    memory_type: str
    content: str
    source: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    importance: int
    created_at: str
    updated_at: str

@router.get("", response_model=List[MemoryResponseSchema])
async def list_memories(
    project_id: Optional[str] = Query(default=None),
    memory_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100)
):
    memories = await memory_manager.retrieve(project_id=project_id, memory_type=memory_type, limit=limit)
    return [
        MemoryResponseSchema(
            id=m.id,
            memory_type=m.memory_type,
            content=m.content,
            source=m.source,
            project_id=m.project_id,
            session_id=m.session_id,
            importance=m.importance,
            created_at=m.created_at.isoformat() if m.created_at else "",
            updated_at=m.updated_at.isoformat() if m.updated_at else ""
        )
        for m in memories
    ]

@router.post("", response_model=MemoryResponseSchema)
async def create_memory(data: MemoryCreateSchema):
    try:
        m = await memory_manager.remember(
            memory_type=data.memory_type,
            content=data.content,
            project_id=data.project_id,
            session_id=data.session_id,
            source=data.source,
            importance=data.importance,
            has_evidence=data.has_evidence
        )
        return MemoryResponseSchema(
            id=m.id,
            memory_type=m.memory_type,
            content=m.content,
            source=m.source,
            project_id=m.project_id,
            session_id=m.session_id,
            importance=m.importance,
            created_at=m.created_at.isoformat() if m.created_at else "",
            updated_at=m.updated_at.isoformat() if m.updated_at else ""
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{memory_id}", response_model=MemoryResponseSchema)
async def get_memory(memory_id: str):
    m = await memory_manager.store.get_by_id(memory_id)
    if not m:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return MemoryResponseSchema(
        id=m.id,
        memory_type=m.memory_type,
        content=m.content,
        source=m.source,
        project_id=m.project_id,
        session_id=m.session_id,
        importance=m.importance,
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else ""
    )

@router.put("/{memory_id}", response_model=MemoryResponseSchema)
async def update_memory(memory_id: str, data: MemoryUpdateSchema):
    try:
        m = await memory_manager.update(memory_id=memory_id, content=data.content, importance=data.importance)
        if not m:
            raise HTTPException(status_code=404, detail="Memory record not found")
        return MemoryResponseSchema(
            id=m.id,
            memory_type=m.memory_type,
            content=m.content,
            source=m.source,
            project_id=m.project_id,
            session_id=m.session_id,
            importance=m.importance,
            created_at=m.created_at.isoformat() if m.created_at else "",
            updated_at=m.updated_at.isoformat() if m.updated_at else ""
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    success = await memory_manager.delete(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"message": "Memory deleted successfully", "id": memory_id}
