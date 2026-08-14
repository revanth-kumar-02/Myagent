import logging
import uuid
import asyncio
import os
from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.future import select

from api.websocket import ws_manager
from db.session import AsyncSessionLocal
from db.models import PermissionAuditLog

logger = logging.getLogger(__name__)

class PermissionLevel(str, Enum):
    FILESYSTEM_READ = "FILESYSTEM_READ"
    FILESYSTEM_WRITE = "FILESYSTEM_WRITE"
    FILESYSTEM_DELETE = "FILESYSTEM_DELETE"
    READ = "READ"  # Alias
    WRITE = "WRITE"  # Alias
    DELETE = "DELETE"  # Alias

    BROWSER_READ = "BROWSER_READ"
    BROWSER_INTERACT = "BROWSER_INTERACT"
    BROWSER_DOWNLOAD = "BROWSER_DOWNLOAD"
    BROWSER_EXTERNAL_ACTION = "BROWSER_EXTERNAL_ACTION"

    AUTOMATION_EXECUTE = "AUTOMATION_EXECUTE"

class PermissionScope(str, Enum):
    ONCE = "ONCE"
    TASK = "TASK"
    SESSION = "SESSION"

class PermissionRequest:
    def __init__(
        self,
        request_id: str,
        tool_name: str,
        path: str,
        operation: str,
        permission_level: PermissionLevel,
        scope: PermissionScope = PermissionScope.ONCE,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        self.request_id = request_id
        self.tool_name = tool_name
        self.path = path
        self.operation = operation
        self.permission_level = permission_level
        self.scope = scope
        self.task_id = task_id
        self.project_id = project_id
        self.status = "pending"  # pending, granted, denied, blocked
        self.future: asyncio.Future = asyncio.get_event_loop().create_future()

def sanitize_resource_log(resource: str) -> str:
    """Removes sensitive credentials or secrets before logging."""
    if not resource:
        return ""
    import re
    cleaned = re.sub(r"(key|token|password|secret|auth)=[^&\s]+", r"\1=••••", resource, flags=re.IGNORECASE)
    cleaned = re.sub(r"gsk_[a-zA-Z0-9_-]{20,}", "gsk_••••", cleaned)
    cleaned = re.sub(r"sk-[a-zA-Z0-9_-]{20,}", "sk-••••", cleaned)
    cleaned = re.sub(r"tvly-[a-zA-Z0-9_-]{20,}", "tvly-••••", cleaned)
    return cleaned

class PermissionManager:
    """Hardened, centralized, auditable Permission Manager for Cocoa Agent."""
    
    def __init__(self, auto_approve_writes: bool = True):
        self.auto_approve_writes = auto_approve_writes
        self.pending_requests: Dict[str, PermissionRequest] = {}
        # Active scope permissions: (scope_type, scope_id, tool_name, normalized_resource, level)
        self.granted_scopes: set[Tuple[str, str, str, str, str]] = set()
        # Denial retry lockout counter: (task_id or 'global', resource, level) -> attempt_count
        self.denial_counters: Dict[Tuple[str, str, str], int] = {}
        # Authorized workspace boundaries: project_id -> list of root absolute paths
        self.project_paths: Dict[str, List[str]] = {}

    def register_project_boundary(self, project_id: str, root_path: str):
        """Registers authorized directory boundaries for a project."""
        norm_path = os.path.abspath(root_path)
        if project_id not in self.project_paths:
            self.project_paths[project_id] = []
        if norm_path not in self.project_paths[project_id]:
            self.project_paths[project_id].append(norm_path)

    async def log_audit(
        self,
        tool_name: str,
        operation: str,
        resource: str,
        permission_level: str,
        decision: str,
        scope: str = "ONCE",
        task_id: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        """Persists permission audit record to database."""
        safe_resource = sanitize_resource_log(resource)
        try:
            async with AsyncSessionLocal() as db:
                entry = PermissionAuditLog(
                    tool_name=tool_name,
                    operation=operation,
                    resource=safe_resource,
                    permission_level=permission_level,
                    decision=decision,
                    scope=scope,
                    task_id=task_id,
                    project_id=project_id,
                    timestamp=datetime.utcnow()
                )
                db.add(entry)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to log permission audit: {e}")

    async def check_permission(
        self,
        tool_name: str,
        path: str,
        operation: str,
        permission_level: PermissionLevel,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: PermissionScope = PermissionScope.ONCE
    ) -> bool:
        """
        Evaluates system, filesystem, browser, and automation permissions.
        Returns True if granted, False if denied/blocked.
        """
        norm_resource = os.path.abspath(path) if (path and "/" in path) else (path or "global")

        # 1. PATH-SCOPED SECURITY & CROSS-PROJECT ISOLATION CHECK
        if project_id and project_id in self.project_paths and path and "/" in path:
            allowed_roots = self.project_paths[project_id]
            is_inside_project = any(
                norm_resource.startswith(root) for root in allowed_roots
            )
            if not is_inside_project:
                logger.warning(f"SECURITY REJECTION: Path '{norm_resource}' outside project '{project_id}' boundaries {allowed_roots}")
                await self.log_audit(tool_name, operation, path, permission_level.value, "blocked", scope.value, task_id, project_id)
                return False

        # 2. RETRY LOCKOUT CHECK (Prevents infinite permission retry loops)
        retry_key = (task_id or "global", norm_resource, permission_level.value)
        if self.denial_counters.get(retry_key, 0) >= 2:
            logger.warning(f"DENIAL LOCKOUT: Operation '{permission_level.value}' on '{norm_resource}' blocked due to repeated denials.")
            await self.log_audit(tool_name, operation, path, permission_level.value, "blocked", scope.value, task_id, project_id)
            return False

        # 3. TASK / SESSION SCOPE CHECK
        if task_id and ("TASK", task_id, tool_name, norm_resource, permission_level.value) in self.granted_scopes:
            await self.log_audit(tool_name, operation, path, permission_level.value, "granted", "TASK", task_id, project_id)
            return True
        if project_id and ("SESSION", project_id, tool_name, norm_resource, permission_level.value) in self.granted_scopes:
            await self.log_audit(tool_name, operation, path, permission_level.value, "granted", "SESSION", task_id, project_id)
            return True

        # 4. SAFE AUTO-APPROVALS (Read-only operations)
        if permission_level in (PermissionLevel.READ, PermissionLevel.FILESYSTEM_READ, PermissionLevel.BROWSER_READ):
            await self.log_audit(tool_name, operation, path, permission_level.value, "granted", scope.value, task_id, project_id)
            return True

        # 5. WRITE & BROWSER_INTERACT AUTO-APPROVAL (if enabled)
        if permission_level in (PermissionLevel.WRITE, PermissionLevel.FILESYSTEM_WRITE, PermissionLevel.BROWSER_INTERACT) and self.auto_approve_writes:
            await self.log_audit(tool_name, operation, path, permission_level.value, "granted", scope.value, task_id, project_id)
            return True

        # 6. DANGEROUS OPERATIONS REQUIRE EXPLICIT USER APPROVAL
        # Includes: FILESYSTEM_DELETE, BROWSER_EXTERNAL_ACTION, BROWSER_DOWNLOAD, AUTOMATION_EXECUTE
        request_id = f"perm-{uuid.uuid4().hex[:8]}"
        req = PermissionRequest(
            request_id=request_id,
            tool_name=tool_name,
            path=path,
            operation=operation,
            permission_level=permission_level,
            scope=scope,
            task_id=task_id,
            project_id=project_id
        )
        self.pending_requests[request_id] = req

        # Broadcast permission request via WebSocket to Desktop UI
        await ws_manager.broadcast({
            "event": "permission.requested",
            "data": {
                "request_id": request_id,
                "tool": tool_name,
                "path": path,
                "operation": operation,
                "permission_level": permission_level.value,
                "scope": scope.value,
                "task_id": task_id,
                "project_id": project_id
            }
        })

        # Wait for explicit user response or timeout
        try:
            is_granted = await asyncio.wait_for(req.future, timeout=10.0)
            if is_granted:
                if scope == PermissionScope.TASK and task_id:
                    self.granted_scopes.add(("TASK", task_id, tool_name, norm_resource, permission_level.value))
                elif scope == PermissionScope.SESSION and project_id:
                    self.granted_scopes.add(("SESSION", project_id, tool_name, norm_resource, permission_level.value))
                await self.log_audit(tool_name, operation, path, permission_level.value, "granted", scope.value, task_id, project_id)
            else:
                self.denial_counters[retry_key] = self.denial_counters.get(retry_key, 0) + 1
                await self.log_audit(tool_name, operation, path, permission_level.value, "denied", scope.value, task_id, project_id)
            return is_granted
        except asyncio.TimeoutError:
            logger.warning(f"Permission request {request_id} timed out. Denying operation.")
            req.status = "denied"
            self.denial_counters[retry_key] = self.denial_counters.get(retry_key, 0) + 1
            await self.log_audit(tool_name, operation, path, permission_level.value, "denied", scope.value, task_id, project_id)
            await ws_manager.broadcast({
                "event": "permission.denied",
                "data": {"request_id": request_id, "reason": "Timeout waiting for user approval"}
            })
            return False
        finally:
            self.pending_requests.pop(request_id, None)

    def respond_permission(self, request_id: str, granted: bool, scope: Optional[PermissionScope] = None) -> bool:
        """
        Receives explicit permission decision from Desktop UI.
        Only genuine user interactions via API/WebSocket can trigger this.
        """
        req = self.pending_requests.get(request_id)
        if not req:
            return False

        if scope:
            req.scope = scope

        req.status = "granted" if granted else "denied"
        if not req.future.done():
            req.future.set_result(granted)

        asyncio.create_task(
            ws_manager.broadcast({
                "event": "permission.granted" if granted else "permission.denied",
                "data": {"request_id": request_id, "granted": granted, "scope": req.scope.value}
            })
        )
        return True

permission_manager = PermissionManager()
