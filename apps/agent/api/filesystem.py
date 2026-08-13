from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from core.filesystem.permission_manager import permission_manager
from core.filesystem.tools import ListDirectoryInput
from core.tools.registry import global_filesystem_toolset

router = APIRouter(prefix="/filesystem", tags=["Filesystem"])

class PermissionResponseRequest(BaseModel):
    request_id: str = Field(..., description="ID of pending permission request")
    granted: bool = Field(..., description="True to grant permission, False to deny")

@router.post("/permissions/respond")
async def respond_to_permission(req: PermissionResponseRequest):
    """Responds to a pending permission approval prompt (e.g. for write or delete)."""
    success = permission_manager.respond_permission(req.request_id, req.granted)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pending permission request '{req.request_id}' not found or already processed.")
    return {"status": "success", "request_id": req.request_id, "granted": req.granted}

@router.get("/browse")
async def safe_browse_directory(
    path: str = Query(".", description="Directory path within authorized workspace"),
    limit: int = Query(100, description="Max entries to return"),
    offset: int = Query(0, description="Pagination offset")
):
    """Safely browse directory contents strictly within authorized workspace roots."""
    input_data = ListDirectoryInput(path=path, limit=limit, offset=offset)
    res = await global_filesystem_toolset.list_directory(input_data)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["error"]["message"])
    return res["result"]
