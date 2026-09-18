"""
tools.types — Tool system type definitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR   = "error"


@dataclass
class ToolResult:
    tool_name: str
    call_id: uuid.UUID
    status: ToolStatus
    output: Any
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == ToolStatus.SUCCESS
