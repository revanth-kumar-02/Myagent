"""
permissions.gate — Permission Gate

Responsibilities:
  - Evaluate whether a tool call is allowed, requires user approval, or is denied
  - Send PERMISSION_REQUEST to client and await PERMISSION_RESPONSE via WebSocket
  - Apply per-project and global permission rules from settings
  - Cache granted approvals for the duration of a session

Decision logic:
  1. If tool.name not in project config permission rules → use global defaults
  2. If global default is ALLOW → pass through immediately
  3. If global default is PROMPT (and not already approved this session) → send PERMISSION_REQUEST WS message, await response
  4. If global default is DENY → raise PermissionDeniedError immediately
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Awaitable, TYPE_CHECKING

import structlog

from config import settings
from permissions.types import PermissionDecision, PermissionGrant, PermissionRequest

if TYPE_CHECKING:
    from tools.base import BaseTool

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict], Awaitable[None]]


class PermissionGate:
    """
    Stateful per-session permission gate.
    Holds a cache of previously granted approvals for this session.
    """

    def __init__(self, ws_send: WSSend) -> None:
        self._ws_send = ws_send
        self._session_grants: set[str] = set()   # tool names approved this session
        self._pending: dict[uuid.UUID, asyncio.Future[bool]] = {}

    async def check(self, tool: "BaseTool") -> None:
        """
        Check permission for a tool. Raises PermissionDeniedError if denied.
        Blocks (awaits user response) if approval is needed.
        """
        # Already approved this session → pass through
        if tool.name in self._session_grants:
            return

        decision = self._resolve_decision(tool)

        match decision:
            case PermissionDecision.ALLOW:
                return
            case PermissionDecision.DENY:
                raise PermissionDeniedError(f"Tool {tool.name!r} is not permitted")
            case PermissionDecision.PROMPT:
                await self._prompt_user(tool)

    def receive_grant(self, grant: PermissionGrant) -> None:
        """
        Called by the WebSocket handler when a PERMISSION_RESPONSE arrives.
        Resolves the pending future for the waiting check() call.
        """
        future = self._pending.pop(grant.request_id, None)
        if future and not future.done():
            future.set_result(grant.granted)

    # ── Private helpers (stubs) ────────────────────────────────────────────────

    def _resolve_decision(self, tool: "BaseTool") -> PermissionDecision:
        """Determine the permission decision for a tool using settings."""
        if tool.name in settings.require_approval_for:
            return PermissionDecision.PROMPT
        return PermissionDecision.ALLOW

    async def _prompt_user(self, tool: "BaseTool") -> None:
        """Send PERMISSION_REQUEST WS frame and await user decision."""
        raise NotImplementedError  # TODO: implement in feature phase


class PermissionDeniedError(Exception):
    """Raised when the PermissionGate blocks a tool call."""
