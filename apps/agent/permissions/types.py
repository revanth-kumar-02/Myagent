"""
permissions.types — Permission system type definitions (V8).
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from tools.types import PermissionLevel


class PermissionDecision(str, enum.Enum):
    ALLOW  = "allow"
    PROMPT = "prompt"   # requires user approval at runtime
    DENY   = "deny"


@dataclass
class PermissionRequest:
    """Sent to client when a tool requires runtime user approval."""
    request_id: uuid.UUID
    tool_name: str
    action: str
    scope: str
    description: str
    permission_level: PermissionLevel = PermissionLevel.HIGH_IMPACT_ACTION


@dataclass
class PermissionGrant:
    """Received from client after user makes an approval decision."""
    request_id: uuid.UUID
    granted: bool
