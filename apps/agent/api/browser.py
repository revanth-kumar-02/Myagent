from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from core.browser.session_manager import browser_session_manager
from core.filesystem.permission_manager import permission_manager

router = APIRouter(prefix="/browser", tags=["browser"])

class PermissionResponseInput(BaseModel):
    request_id: str = Field(description="Permission request ID")
    granted: bool = Field(description="Whether the user granted permission")

@router.get("/sessions")
async def list_browser_sessions():
    sessions_data = []
    for sid, session in browser_session_manager.sessions.items():
        sessions_data.append({
            "session_id": sid,
            "task_id": session.task_id,
            "created_at": session.created_at,
            "active_page_id": session.active_page_id,
            "pages_count": len(session.pages),
            "domains": [d.to_dict() for d in session.domain_history.values()]
        })
    return {"sessions": sessions_data, "count": len(sessions_data)}

@router.get("/sessions/{session_id}")
async def get_browser_session(session_id: str):
    session = browser_session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    pages = []
    for pid, page in session.pages.items():
        pages.append({
            "page_id": pid,
            "url": page.url,
            "is_closed": page.is_closed()
        })

    return {
        "session_id": session.session_id,
        "task_id": session.task_id,
        "created_at": session.created_at,
        "active_page_id": session.active_page_id,
        "pages": pages,
        "domains": [d.to_dict() for d in session.domain_history.values()]
    }

@router.delete("/sessions/{session_id}")
async def close_browser_session(session_id: str):
    if session_id not in browser_session_manager.sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await browser_session_manager.close_session(session_id)
    return {"status": "success", "message": f"Session '{session_id}' closed"}

@router.post("/permissions/respond")
async def respond_browser_permission(body: PermissionResponseInput):
    success = permission_manager.respond_permission(body.request_id, body.granted)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pending permission request '{body.request_id}' not found")
    return {"status": "success", "request_id": body.request_id, "granted": body.granted}
