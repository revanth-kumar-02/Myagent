"""
permissions.types — Permission system type definitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class PermissionDecision(str, Enum):
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


@dataclass
class PermissionGrant:
    """Received from client after user makes an approval decision."""
    request_id: uuid.UUID
    granted: bool
