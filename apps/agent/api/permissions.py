from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.future import select

from core.filesystem.permission_manager import permission_manager, PermissionScope
from db.session import AsyncSessionLocal
from db.models import PermissionAuditLog

router = APIRouter(prefix="/permissions", tags=["permissions"])

class PermissionDecisionSchema(BaseModel):
    request_id: str = Field(description="ID of pending permission request")
    granted: bool = Field(description="Decision: true to grant, false to deny")
    scope: Optional[str] = Field(default="ONCE", description="ONCE | TASK | SESSION")

class AuditLogResponseSchema(BaseModel):
    id: str
    tool_name: str
    operation: str
    resource: str
    permission_level: str
    decision: str
    scope: str
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    timestamp: str

@router.post("/respond")
async def respond_permission(data: PermissionDecisionSchema):
    scope_enum = PermissionScope.ONCE
    if data.scope:
        try:
            scope_enum = PermissionScope(data.scope.upper())
        except ValueError:
            pass

    success = permission_manager.respond_permission(data.request_id, data.granted, scope=scope_enum)
    if not success:
        raise HTTPException(status_code=404, detail=f"Permission request '{data.request_id}' not found or already processed.")
    return {"status": "success", "request_id": data.request_id, "granted": data.granted, "scope": scope_enum.value}

@router.get("/audit-logs", response_model=List[AuditLogResponseSchema])
async def get_audit_logs(limit: int = Query(default=50, ge=1, le=200)):
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PermissionAuditLog)
            .order_by(PermissionAuditLog.timestamp.desc())
            .limit(limit)
        )
        logs = res.scalars().all()
        return [
            AuditLogResponseSchema(
                id=log.id,
                tool_name=log.tool_name,
                operation=log.operation,
                resource=log.resource,
                permission_level=log.permission_level,
                decision=log.decision,
                scope=log.scope,
                task_id=log.task_id,
                project_id=log.project_id,
                timestamp=log.timestamp.isoformat() if log.timestamp else ""
            )
            for log in logs
        ]
