"""
tools.types — Tool System Domain Models and Type Definitions (V8)
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ToolCategory(str, enum.Enum):
    """Broad category for organizing and filtering tools."""
    SYSTEM      = "system"       # Launcher, clipboard, notifications, sysinfo
    FILES       = "files"        # Read, write, create, move, rename, delete, directories
    COMPUTER    = "computer"     # Windows, mouse, keyboard, screen capture
    WEB         = "web"          # Browser control, navigation, interaction, downloads
    DEVELOPMENT = "development"  # Terminal, git, database queries


class PermissionLevel(str, enum.Enum):
    """
    4-Tier Permission Classification:
      READ                → Safe, idempotent inspection (e.g. file read, sysinfo)
      LOW_RISK_WRITE      → Minor local modifications (e.g. clipboard, file create/write)
      EXTERNAL_ACTION     → Interactions with external networks/APIs (e.g. web navigation, downloads)
      HIGH_IMPACT_ACTION  → Potentially destructive/elevated actions (e.g. file delete, terminal commands, database mutations)
    """
    READ                = "read"
    LOW_RISK_WRITE      = "low_risk_write"
    EXTERNAL_ACTION     = "external_action"
    HIGH_IMPACT_ACTION  = "high_impact_action"


class PlatformOS(str, enum.Enum):
    """Supported operating systems."""
    LINUX   = "linux"
    WINDOWS = "windows"
    MACOS   = "macos"
    ALL     = "all"


class ToolStatus(str, enum.Enum):
    """Execution status of a tool invocation."""
    SUCCESS           = "success"
    ERROR             = "error"
    TIMEOUT           = "timeout"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ToolResult:
    """Structured result returned by every tool invocation."""
    tool_name: str
    call_id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: ToolStatus = ToolStatus.SUCCESS
    output: Any = None
    error: str | None = None
    execution_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ToolStatus.SUCCESS


@dataclass
class AuditRecord:
    """Audit log entry for tool executions."""
    tool_id: str
    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    permission_level: PermissionLevel = PermissionLevel.READ
    status: ToolStatus = ToolStatus.SUCCESS
    error: str | None = None
    execution_duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
