"""
tools.base — BaseTool Abstract Class

Every tool in the Kora tool system must implement this interface.
Tools are self-describing: they declare their name, description,
JSON Schema parameters, and required permissions.
"""

from __future__ import annotations

import abc
import uuid
from typing import Any

from tools.types import ToolResult


class BaseTool(abc.ABC):
    """Abstract base for all Kora tools."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique tool identifier. Used in registry and WS messages."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""

    @property
    @abc.abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema object describing accepted parameters."""

    @property
    def required_permissions(self) -> list[str]:
        """
        Permission strings required before this tool can execute.
        Empty list means no approval needed.
        """
        return []

    @abc.abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given parameters.
        Must return a ToolResult — never raise directly.
        """

    def _make_result(
        self,
        output: Any,
        call_id: uuid.UUID | None = None,
        error: str | None = None,
    ) -> ToolResult:
        from tools.types import ToolStatus
        return ToolResult(
            tool_name=self.name,
            call_id=call_id or uuid.uuid4(),
            status=ToolStatus.ERROR if error else ToolStatus.SUCCESS,
            output=output,
            error=error,
        )
