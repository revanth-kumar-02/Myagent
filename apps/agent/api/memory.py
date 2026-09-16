from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.memory import memory_manager

router = APIRouter(prefix="/memories", tags=["memories"])

class MemoryCreateSchema(BaseModel):
    memory_type: str = Field(default="PROJECT_KNOWLEDGE", description="FACT | DECISION | PREFERENCE | PROJECT_KNOWLEDGE | RESEARCH_FINDING | TASK_OUTCOME | TECHNICAL_CONTEXT | USER_PREFERENCE")
    content: str = Field(description="Memory text content")
    project_id: Optional[str] = Field(default=None, description="Associated project ID")
    session_id: Optional[str] = Field(default=None, description="Associated session ID")
    source: str = Field(default="user", description="Source description")
    source_reliability: str = Field(default="USER_CONFIRMED", description="USER_CONFIRMED | VERIFIED_TASK | VERIFIED_RESEARCH | PROJECT_FILE | GIT_METADATA | AGENT_INFERENCE")
    importance: int = Field(default=5, ge=1, le=10)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_status: str = Field(default="ACTIVE", description="CANDIDATE | VERIFIED | ACTIVE | SUPERSEDED | ARCHIVED")
    has_evidence: bool = Field(default=True, description="Evidence flag for research memories")

class MemorySearchSchema(BaseModel):
    query: str = Field(description="Search query string")
    project_id: Optional[str] = Field(default=None)
    memory_type: Optional[str] = Field(default=None)
    limit: int = Field(default=10, ge=1, le=50)

class MemorySupersedeSchema(BaseModel):
    new_content: str = Field(description="New replacement content")
    project_id: Optional[str] = Field(default=None)
    source: str = Field(default="user")
    source_reliability: str = Field(default="USER_CONFIRMED")

class MemoryUpdateSchema(BaseModel):
    content: Optional[str] = Field(default=None)
    importance: Optional[int] = Field(default=None, ge=1, le=10)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    verification_status: Optional[str] = Field(default=None)

class MemoryResponseSchema(BaseModel):
    id: str
    memory_type: str
    content: str
    source: str
    source_reliability: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    importance: int
    confidence: float
    verification_status: str
    supersedes_id: Optional[str] = None
    created_at: str
    updated_at: str

def format_memory_response(m) -> MemoryResponseSchema:
    return MemoryResponseSchema(
        id=m.id,
        memory_type=m.memory_type,
        content=m.content,
        source=m.source,
        source_reliability=getattr(m, 'source_reliability', 'USER_CONFIRMED'),
        project_id=m.project_id,
        session_id=m.session_id,
        importance=m.importance,
        confidence=getattr(m, 'confidence', 1.0),
        verification_status=getattr(m, 'verification_status', 'ACTIVE'),
        supersedes_id=getattr(m, 'supersedes_id', None),
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else ""
    )

@router.get("", response_model=List[MemoryResponseSchema])
async def list_memories(
    project_id: Optional[str] = Query(default=None),
    memory_type: Optional[str] = Query(default=None),
    verification_status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100)
):
    memories = await memory_manager.store.retrieve(
        project_id=project_id,
        memory_type=memory_type,
        verification_status=verification_status,
        limit=limit
    )
    return [format_memory_response(m) for m in memories]

@router.post("/search", response_model=List[MemoryResponseSchema])
async def search_memories(data: MemorySearchSchema):
    memories = await memory_manager.search(
        query=data.query,
        project_id=data.project_id,
        memory_type=data.memory_type,
        limit=data.limit
    )
    return [format_memory_response(m) for m in memories]

@router.post("", response_model=MemoryResponseSchema)
async def create_memory(data: MemoryCreateSchema):
    try:
        m = await memory_manager.remember(
            memory_type=data.memory_type,
            content=data.content,
            project_id=data.project_id,
            session_id=data.session_id,
            source=data.source,
            source_reliability=data.source_reliability,
            importance=data.importance,
            confidence=data.confidence,
            verification_status=data.verification_status,
            has_evidence=data.has_evidence
        )
        return format_memory_response(m)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{memory_id}", response_model=MemoryResponseSchema)
async def get_memory(memory_id: str):
    m = await memory_manager.get_by_id(memory_id)
    if not m:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return format_memory_response(m)

@router.post("/{memory_id}/verify", response_model=MemoryResponseSchema)
async def verify_memory(memory_id: str):
    m = await memory_manager.verify(memory_id)
    if not m:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return format_memory_response(m)

@router.post("/{memory_id}/supersede", response_model=MemoryResponseSchema)
async def supersede_memory(memory_id: str, data: MemorySupersedeSchema):
    try:
        m = await memory_manager.supersede(
            old_memory_id=memory_id,
            new_content=data.new_content,
            project_id=data.project_id,
            source=data.source,
            source_reliability=data.source_reliability
        )
        return format_memory_response(m)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{memory_id}/archive", response_model=MemoryResponseSchema)
async def archive_memory(memory_id: str):
    m = await memory_manager.archive(memory_id)
    if not m:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return format_memory_response(m)

@router.put("/{memory_id}", response_model=MemoryResponseSchema)
async def update_memory(memory_id: str, data: MemoryUpdateSchema):
    try:
        m = await memory_manager.update(
            memory_id=memory_id,
            content=data.content,
            importance=data.importance,
            confidence=data.confidence,
            verification_status=data.verification_status
        )
        if not m:
            raise HTTPException(status_code=404, detail="Memory record not found")
        return format_memory_response(m)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    success = await memory_manager.delete(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"message": "Memory deleted successfully", "id": memory_id}
