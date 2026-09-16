import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.future import select
from sqlalchemy import func

from db.session import AsyncSessionLocal
from db.models import Project, ProjectFile, ProjectChunk
from core.rag.indexer import project_rag_indexer
from core.rag.retriever import project_rag_retriever, SearchResultChunk
from core.rag.context_builder import project_context_builder, ProjectContextResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Project RAG"])

class IndexProjectRequest(BaseModel):
    project_id: str
    workspace_path: Optional[str] = None
    force_full: bool = False

class RagSearchRequest(BaseModel):
    project_id: str
    query: str
    limit: int = Field(default=10, ge=1, le=50)
    language: Optional[str] = None
    file_path_filter: Optional[str] = None

class RagContextRequest(BaseModel):
    project_id: str
    query: str
    max_chars: int = Field(default=12000, ge=500, le=50000)
    max_chunks: int = Field(default=8, ge=1, le=30)

class RagRefreshRequest(BaseModel):
    project_id: str

class RagStatusResponse(BaseModel):
    project_id: str
    title: str
    workspace_path: Optional[str] = None
    indexing_status: str
    total_files: int
    total_chunks: int
    languages: List[str]
    last_indexed: Optional[str] = None
    vector_backend: str

@router.post("/rag/index")
async def index_project_rag(req: IndexProjectRequest):
    """
    Trigger full or incremental structural RAG indexing for a project workspace.
    """
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    result = await project_rag_indexer.index_project(
        project_id=req.project_id,
        workspace_path=req.workspace_path,
        force_full=req.force_full
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Indexing failed"))

    return result

@router.get("/rag/status", response_model=RagStatusResponse)
async def get_rag_status(project_id: str = Query(..., description="Project UUID")):
    """
    Retrieve current RAG index metrics, chunk counts, and vector backend status.
    """
    async with AsyncSessionLocal() as db:
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        proj = proj_res.scalar_one_or_none()
        if not proj:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

        # Count files
        files_count_res = await db.execute(
            select(func.count()).select_from(ProjectFile).where(ProjectFile.project_id == project_id)
        )
        total_files = files_count_res.scalar() or 0

        # Count chunks
        chunks_count_res = await db.execute(
            select(func.count()).select_from(ProjectChunk).where(ProjectChunk.project_id == project_id)
        )
        total_chunks = chunks_count_res.scalar() or 0

        # Unique languages in indexed chunks
        lang_res = await db.execute(
            select(ProjectChunk.language).where(ProjectChunk.project_id == project_id).distinct()
        )
        languages = [l for l in lang_res.scalars().all() if l]

    idx_status = "INDEXED" if total_chunks > 0 else "IDLE"
    last_idx = proj.last_scanned.isoformat() if proj.last_scanned else None

    return RagStatusResponse(
        project_id=proj.id,
        title=proj.title,
        workspace_path=proj.path,
        indexing_status=idx_status,
        total_files=total_files,
        total_chunks=total_chunks,
        languages=languages or (proj.languages or []),
        last_indexed=last_idx,
        vector_backend=project_rag_retriever.get_active_vector_backend()
    )

@router.post("/rag/search", response_model=List[SearchResultChunk])
async def search_rag(req: RagSearchRequest):
    """
    Perform hybrid semantic + keyword retrieval scoped strictly to project_id.
    Never exposes raw vector embeddings.
    """
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not req.query.strip():
        return []

    try:
        chunks = await project_rag_retriever.search(
            query=req.query,
            project_id=req.project_id,
            limit=req.limit,
            language=req.language,
            file_path_filter=req.file_path_filter
        )
        return chunks
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"RAG search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

@router.post("/rag/context", response_model=ProjectContextResult)
async def get_rag_context(req: RagContextRequest):
    """
    Build bounded, deduplicated project context from highest-relevance chunks.
    """
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    result = await project_context_builder.build_project_context(
        project_id=req.project_id,
        query=req.query,
        max_chars=req.max_chars,
        max_chunks=req.max_chunks
    )
    return result

@router.post("/rag/refresh")
async def refresh_project_rag(req: RagRefreshRequest):
    """
    Perform incremental refresh of project workspace knowledge.
    Skips unchanged files based on SHA-256 content hashes.
    """
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    result = await project_rag_indexer.index_project(
        project_id=req.project_id,
        force_full=False
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Refresh failed"))

    return result
