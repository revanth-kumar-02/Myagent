"""
tools.google.sheets_tools — Google Sheets Agent Tools (V8)

Provides granular tools (google_sheets_read, google_sheets_write, google_sheets_append)
and unified tool (google_sheets).
"""

from __future__ import annotations

from typing import Any

from integrations.google.errors import GoogleWorkspaceError
from integrations.google.sheets import SheetsService
from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult, ToolStatus


def _format_google_error(tool_name: str, err: Exception) -> ToolResult:
    """Format exceptions into clean, structured ToolResult."""
    if isinstance(err, GoogleWorkspaceError):
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.ERROR,
            error=err.message,
            output={"error_code": err.error_code, "details": err.details},
        )
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.ERROR,
        error=f"Sheets operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class SheetsReadTool(BaseTool):
    """Read values or rows from a Google Spreadsheet range."""

    def __init__(self, service: SheetsService | None = None) -> None:
        self.service = service or SheetsService()

    @property
    def tool_id(self) -> str:
        return "google_sheets_read"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Read values from a Google Sheets range (e.g. 'Sheet1!A1:D20' or 'A1:B10')."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "Google Spreadsheet ID"},
                "range_notation": {"type": "string", "description": "A1 notation range (e.g. 'Sheet1!A1:D20')"},
            },
            "required": ["spreadsheet_id", "range_notation"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            data = await self.service.read_range(
                spreadsheet_id=p.get("spreadsheet_id", ""),
                range_notation=p.get("range_notation", ""),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=data)
        except Exception as e:
            return _format_google_error(self.name, e)


class SheetsWriteTool(BaseTool):
    """Write/overwrite values into a Google Spreadsheet range (destructive changes)."""

    def __init__(self, service: SheetsService | None = None) -> None:
        self.service = service or SheetsService()

    @property
    def tool_id(self) -> str:
        return "google_sheets_write"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Write or overwrite values into a Google Sheets range (requires confirmation for destructive updates)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "Google Spreadsheet ID"},
                "range_notation": {"type": "string", "description": "Target A1 range (e.g. 'Sheet1!A1:B5')"},
                "values": {
                    "type": "array",
                    "items": {"type": "array", "items": {}},
                    "description": "2D array of rows and cell values",
                },
            },
            "required": ["spreadsheet_id", "range_notation", "values"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            res = await self.service.write_range(
                spreadsheet_id=p.get("spreadsheet_id", ""),
                range_notation=p.get("range_notation", ""),
                values=p.get("values", []),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class SheetsAppendTool(BaseTool):
    """Append rows to a Google Spreadsheet."""

    def __init__(self, service: SheetsService | None = None) -> None:
        self.service = service or SheetsService()

    @property
    def tool_id(self) -> str:
        return "google_sheets_append"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Append new rows of data below existing table content in a Google Spreadsheet."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "Google Spreadsheet ID"},
                "range_notation": {"type": "string", "description": "Target sheet or range (e.g. 'Sheet1' or 'Sheet1!A:D')"},
                "values": {
                    "type": "array",
                    "items": {"type": "array", "items": {}},
                    "description": "2D array of rows to append",
                },
            },
            "required": ["spreadsheet_id", "range_notation", "values"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            res = await self.service.append_rows(
                spreadsheet_id=p.get("spreadsheet_id", ""),
                range_notation=p.get("range_notation", ""),
                values=p.get("values", []),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleSheetsTool(BaseTool):
    """Unified Google Sheets multi-action tool."""

    def __init__(self, service: SheetsService | None = None) -> None:
        self.service = service or SheetsService()

    @property
    def tool_id(self) -> str:
        return "google_sheets"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Interact with Google Sheets: read ranges, write cells, append rows, create spreadsheets, or add sheets."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "append", "create", "metadata", "add_sheet"],
                    "description": "Sheets action to perform",
                },
                "spreadsheet_id": {"type": "string", "description": "Google Spreadsheet ID"},
                "range_notation": {"type": "string", "description": "Range notation (e.g. 'Sheet1!A1:D20')"},
                "values": {
                    "type": "array",
                    "items": {"type": "array", "items": {}},
                    "description": "2D array of cell rows",
                },
                "title": {"type": "string", "description": "Title for spreadsheet or new sheet creation"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "read")
        spreadsheet_id = p.get("spreadsheet_id", "")

        try:
            if action == "read":
                res = await self.service.read_range(
                    spreadsheet_id=spreadsheet_id,
                    range_notation=p.get("range_notation", "Sheet1!A1:Z100"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "metadata":
                res = await self.service.get_spreadsheet(spreadsheet_id=spreadsheet_id)
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "write":
                res = await self.service.write_range(
                    spreadsheet_id=spreadsheet_id,
                    range_notation=p.get("range_notation", ""),
                    values=p.get("values", []),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "append":
                res = await self.service.append_rows(
                    spreadsheet_id=spreadsheet_id,
                    range_notation=p.get("range_notation", ""),
                    values=p.get("values", []),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "create":
                res = await self.service.create_spreadsheet(title=p.get("title", "Untitled Spreadsheet"))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "add_sheet":
                res = await self.service.add_sheet(
                    spreadsheet_id=spreadsheet_id,
                    title=p.get("title", "New Sheet"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Unknown action: {action}",
                    output={"error_code": "GOOGLE_INVALID_ARGUMENT"},
                )
        except Exception as e:
            return _format_google_error(self.name, e)
