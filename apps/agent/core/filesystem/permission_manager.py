import logging
import uuid
import asyncio
from enum import Enum
from typing import Dict, Any, Optional
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

class PermissionLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    BROWSER_READ = "BROWSER_READ"
    BROWSER_INTERACT = "BROWSER_INTERACT"
    BROWSER_DOWNLOAD = "BROWSER_DOWNLOAD"
    BROWSER_EXTERNAL_ACTION = "BROWSER_EXTERNAL_ACTION"

class PermissionRequest:
    def __init__(
        self,
        request_id: str,
        tool_name: str,
        path: str,
        operation: str,
        permission_level: PermissionLevel,
        task_id: Optional[str] = None
    ):
        self.request_id = request_id
        self.tool_name = tool_name
        self.path = path
        self.operation = operation
        self.permission_level = permission_level
        self.task_id = task_id
        self.status = "pending"  # pending, granted, denied
        self.future: asyncio.Future = asyncio.get_event_loop().create_future()

class PermissionManager:
    def __init__(self, auto_approve_writes: bool = True):
        self.auto_approve_writes = auto_approve_writes
        self.pending_requests: Dict[str, PermissionRequest] = {}

    async def check_permission(
        self,
        tool_name: str,
        path: str,
        operation: str,
        permission_level: PermissionLevel,
        task_id: Optional[str] = None
    ) -> bool:
        """
        Evaluates system & browser permissions for operations.
        Returns True if granted, False if denied.
        """
        # 1. Standard READ and BROWSER_READ are auto-approved
        if permission_level in (PermissionLevel.READ, PermissionLevel.BROWSER_READ):
            return True

        # 2. WRITE & BROWSER_INTERACT can auto-approve if configured
        if permission_level in (PermissionLevel.WRITE, PermissionLevel.BROWSER_INTERACT) and self.auto_approve_writes:
            logger.info(f"Auto-approved {permission_level.value} for {tool_name} on {path}")
            return True

        # 3. DELETE, BROWSER_DOWNLOAD, and BROWSER_EXTERNAL_ACTION require explicit approval or prompt
        request_id = f"perm-{uuid.uuid4().hex[:8]}"
        req = PermissionRequest(
            request_id=request_id,
            tool_name=tool_name,
            path=path,
            operation=operation,
            permission_level=permission_level,
            task_id=task_id
        )
        self.pending_requests[request_id] = req

        # Broadcast permission request via WebSocket
        await ws_manager.broadcast({
            "event": "tool.permission_requested" if not tool_name.startswith("browser_") else "browser.permission_requested",
            "data": {
                "request_id": request_id,
                "tool": tool_name,
                "path": path,
                "operation": operation,
                "permission_level": permission_level.value,
                "task_id": task_id
            }
        })

        # Wait for resolution or timeout (default 10 seconds for test/interactive response)
        try:
            is_granted = await asyncio.wait_for(req.future, timeout=10.0)
            return is_granted
        except asyncio.TimeoutError:
            logger.warning(f"Permission request {request_id} timed out. Denying operation.")
            req.status = "denied"
            event_name = "browser.permission_denied" if tool_name.startswith("browser_") else "tool.permission_denied"
            await ws_manager.broadcast({
                "event": event_name,
                "data": {"request_id": request_id, "reason": "Timeout waiting for user approval"}
            })
            return False
        finally:
            self.pending_requests.pop(request_id, None)

    def respond_permission(self, request_id: str, granted: bool):
        req = self.pending_requests.get(request_id)
        if not req:
            return False

        req.status = "granted" if granted else "denied"
        if not req.future.done():
            req.future.set_result(granted)

        tool_name = req.tool_name
        is_browser = tool_name.startswith("browser_")
        event_granted = "browser.permission_granted" if is_browser else "tool.permission_granted"
        event_denied = "browser.permission_denied" if is_browser else "tool.permission_denied"

        asyncio.create_task(
            ws_manager.broadcast({
                "event": event_granted if granted else event_denied,
                "data": {"request_id": request_id, "granted": granted}
            })
        )
        return True

permission_manager = PermissionManager()
