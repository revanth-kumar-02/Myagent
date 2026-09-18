"""
permissions.gate — Permission Gate (V8)

Responsibilities:
  - Evaluate whether a tool call is allowed, requires user approval, or is denied
  - Send PERMISSION_REQUEST to client and await PERMISSION_RESPONSE via WebSocket
  - Enforce 4-tier permission policy (READ, LOW_RISK_WRITE, EXTERNAL_ACTION, HIGH_IMPACT_ACTION)
  - Cache granted approvals for the duration of a session
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Awaitable, Callable

import structlog

from config import settings
from permissions.types import PermissionDecision, PermissionGrant, PermissionRequest
from tools.types import PermissionLevel

if TYPE_CHECKING:
    from tools.base import BaseTool

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict], Awaitable[None]]


class PermissionDeniedError(Exception):
    """Raised when the PermissionGate blocks a tool call."""


class PermissionGate:
    """
    Stateful per-session permission gate.
    Holds a cache of previously granted approvals for this session.
    """

    def __init__(self, ws_send: WSSend | None = None) -> None:
        self._ws_send = ws_send
        self._session_grants: set[str] = set()   # tool names approved this session
        self._pending: dict[uuid.UUID, asyncio.Future[bool]] = {}

    async def check(self, tool: "BaseTool") -> None:
        """
        Check permission for a tool. Raises PermissionDeniedError if denied.
        Blocks (awaits user response) if approval is needed.
        """
        # Already approved this session → pass through
        if tool.name in self._session_grants or getattr(tool, "tool_id", tool.name) in self._session_grants:
            return

        decision = self._resolve_decision(tool)

        match decision:
            case PermissionDecision.ALLOW:
                return
            case PermissionDecision.DENY:
                raise PermissionDeniedError(f"Tool {tool.name!r} is denied by policy")
            case PermissionDecision.PROMPT:
                await self._prompt_user(tool)

    def grant_for_session(self, tool_name: str) -> None:
        """Manually grant permission for a tool name for the remainder of this session."""
        self._session_grants.add(tool_name)

    def receive_grant(self, grant: PermissionGrant) -> None:
        """
        Called when a PERMISSION_RESPONSE arrives.
        Resolves the pending future for the waiting check() call.
        """
        future = self._pending.pop(grant.request_id, None)
        if future and not future.done():
            future.set_result(grant.granted)

    def _resolve_decision(self, tool: "BaseTool") -> PermissionDecision:
        """Determine the permission decision for a tool."""
        # 1. Explicit tool list in settings
        require_approval = getattr(settings, "require_approval_for", ["shell_exec", "terminal_exec", "file_delete", "database_ops"])
        if tool.name in require_approval:
            return PermissionDecision.PROMPT

        # 2. Permission level check
        perm_level = getattr(tool, "permission_level", PermissionLevel.READ)
        if perm_level == PermissionLevel.HIGH_IMPACT_ACTION:
            return PermissionDecision.PROMPT

        return PermissionDecision.ALLOW

    async def _prompt_user(self, tool: "BaseTool") -> None:
        """Send PERMISSION_REQUEST WS frame and await user decision."""
        if self._ws_send is None:
            # When no WS client is attached (e.g. CLI or background worker without prompt capability),
            # check if default prompt is treated as denied
            logger.warning("no_ws_connection_for_prompt", tool=tool.name)
            raise PermissionDeniedError(f"Tool {tool.name!r} requires approval but no interactive client connected.")

        req_id = uuid.uuid4()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[req_id] = future

        await self._ws_send({
            "type": "PERMISSION_REQUEST",
            "payload": {
                "request_id": str(req_id),
                "tool_name": tool.name,
                "permission_level": getattr(tool, "permission_level", PermissionLevel.HIGH_IMPACT_ACTION).value,
                "description": tool.description,
            },
        })

        try:
            granted = await asyncio.wait_for(future, timeout=60.0)
            if not granted:
                raise PermissionDeniedError(f"User rejected permission request for tool {tool.name!r}")
            self._session_grants.add(tool.name)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise PermissionDeniedError(f"Permission request for {tool.name!r} timed out after 60s")
