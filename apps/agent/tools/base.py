"""
tools.base — BaseTool Abstract Class (V8)

Every tool in Kora implements this self-describing, validated interface.
Features:
  - Strict input and output JSON schema declaration
  - Category and 4-tier PermissionLevel classification
  - Platform OS support declaration
  - Parameter validation against required schema fields
  - Automatic timeout enforcement via asyncio.wait_for
  - Execution duration measurement and Audit Logging hooks
"""

from __future__ import annotations

import abc
import asyncio
import sys
import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from tools.types import PermissionLevel, PlatformOS, ToolCategory, ToolResult, ToolStatus

if TYPE_CHECKING:
    from tools.audit import ToolAuditLogger

logger = structlog.get_logger(__name__)


class ToolValidationError(ValueError):
    """Raised when tool arguments fail parameter validation."""


class ToolPlatformError(RuntimeError):
    """Raised when a tool is executed on an unsupported operating system."""


class BaseTool(abc.ABC):
    """
    Abstract base class for all Kora tools.
    """

    @property
    @abc.abstractmethod
    def tool_id(self) -> str:
        """Unique identifier (e.g. 'file_read')."""

    @property
    def name(self) -> str:
        """Name used in registry and function-calling schemas (defaults to tool_id)."""
        return self.tool_id

    @property
    @abc.abstractmethod
    def category(self) -> ToolCategory:
        """Tool category (SYSTEM, FILES, COMPUTER, WEB, DEVELOPMENT)."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""

    @property
    @abc.abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema object describing input parameters."""

    @property
    def output_schema(self) -> dict[str, Any]:
        """JSON Schema object describing expected output."""
        return {"type": "object"}

    @property
    def permission_level(self) -> PermissionLevel:
        """4-Tier permission level (READ, LOW_RISK_WRITE, EXTERNAL_ACTION, HIGH_IMPACT_ACTION)."""
        return PermissionLevel.READ

    @property
    def timeout(self) -> float:
        """Execution timeout in seconds (default 30.0)."""
        return 30.0

    @property
    def platform_support(self) -> list[PlatformOS]:
        """Supported operating systems (defaults to all)."""
        return [PlatformOS.ALL]

    @property
    def available(self) -> bool:
        """Whether this tool is currently available on the host system."""
        return True

    @property
    def requires_network(self) -> bool:
        """Whether this tool requires active Internet connectivity."""
        return self.category == ToolCategory.WEB

    @property
    def available_offline(self) -> bool:
        """Whether this tool is available offline."""
        return not self.requires_network

    def validate_params(self, params: dict[str, Any]) -> None:
        """
        Validates provided parameters against the tool's parameter schema.
        """
        schema = self.parameters
        required = schema.get("required", [])
        for field in required:
            if field not in params or params[field] is None:
                raise ToolValidationError(f"Missing required parameter: {field!r} for tool {self.name!r}")

    async def run(
        self,
        params: dict[str, Any],
        audit_logger: ToolAuditLogger | None = None,
    ) -> ToolResult:
        """
        Validated execution wrapper with timeout, timing, and audit recording.
        """
        start_ns = time.monotonic_ns()
        call_id = uuid.uuid4()

        # 1. Platform check
        current_os = self._get_current_platform_os()
        if PlatformOS.ALL not in self.platform_support and current_os not in self.platform_support:
            err = f"Tool {self.name!r} is not supported on {current_os.value}."
            duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            res = ToolResult(
                tool_name=self.name,
                call_id=call_id,
                status=ToolStatus.ERROR,
                error=err,
                execution_time_ms=duration_ms,
            )
            if audit_logger:
                audit_logger.record(
                    tool_id=self.tool_id,
                    action="execute",
                    permission_level=self.permission_level,
                    status=ToolStatus.ERROR,
                    execution_duration_ms=duration_ms,
                    error=err,
                )
            return res

        # 2. Input validation
        try:
            self.validate_params(params)
        except ToolValidationError as ve:
            duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            res = ToolResult(
                tool_name=self.name,
                call_id=call_id,
                status=ToolStatus.ERROR,
                error=str(ve),
                execution_time_ms=duration_ms,
            )
            if audit_logger:
                audit_logger.record(
                    tool_id=self.tool_id,
                    action="execute",
                    permission_level=self.permission_level,
                    status=ToolStatus.ERROR,
                    execution_duration_ms=duration_ms,
                    error=str(ve),
                )
            return res

        # 3. Execution with timeout
        try:
            result = await asyncio.wait_for(self.execute(params), timeout=self.timeout)
            duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            result.execution_time_ms = duration_ms
            result.call_id = call_id

            if audit_logger:
                audit_logger.record(
                    tool_id=self.tool_id,
                    action="execute",
                    permission_level=self.permission_level,
                    status=result.status,
                    execution_duration_ms=duration_ms,
                    error=result.error,
                    metadata={"params": params},
                )
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            err_msg = f"Tool {self.name!r} timed out after {self.timeout}s."
            res = ToolResult(
                tool_name=self.name,
                call_id=call_id,
                status=ToolStatus.TIMEOUT,
                error=err_msg,
                execution_time_ms=duration_ms,
            )
            if audit_logger:
                audit_logger.record(
                    tool_id=self.tool_id,
                    action="execute",
                    permission_level=self.permission_level,
                    status=ToolStatus.TIMEOUT,
                    execution_duration_ms=duration_ms,
                    error=err_msg,
                )
            return res

        except Exception as e:
            duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            res = ToolResult(
                tool_name=self.name,
                call_id=call_id,
                status=ToolStatus.ERROR,
                error=str(e),
                execution_time_ms=duration_ms,
            )
            if audit_logger:
                audit_logger.record(
                    tool_id=self.tool_id,
                    action="execute",
                    permission_level=self.permission_level,
                    status=ToolStatus.ERROR,
                    execution_duration_ms=duration_ms,
                    error=str(e),
                )
            return res

    @abc.abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Concrete tool implementation. Must return a ToolResult."""

    def _make_result(
        self,
        output: Any = None,
        call_id: uuid.UUID | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Helper constructor for ToolResult."""
        return ToolResult(
            tool_name=self.name,
            call_id=call_id or uuid.uuid4(),
            status=ToolStatus.ERROR if error else ToolStatus.SUCCESS,
            output=output,
            error=error,
            metadata=metadata or {},
        )

    def _get_current_platform_os(self) -> PlatformOS:
        """Detect current PlatformOS."""
        if sys.platform.startswith("win"):
            return PlatformOS.WINDOWS
        elif sys.platform.startswith("darwin"):
            return PlatformOS.MACOS
        return PlatformOS.LINUX
