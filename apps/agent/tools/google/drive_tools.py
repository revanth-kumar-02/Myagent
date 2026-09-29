"""
tools.google.drive_tools — Google Drive Agent Tools (V8)

Provides granular tools (google_drive_search, google_drive_read, google_drive_create_folder,
google_drive_upload, google_drive_delete) and unified (google_drive).
"""

from __future__ import annotations

from typing import Any

from integrations.google.drive import DriveService
from integrations.google.errors import GoogleWorkspaceError
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
        error=f"Drive operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class DriveSearchTool(BaseTool):
    """Search files in Google Drive."""

    def __init__(self, service: DriveService | None = None) -> None:
        self.service = service or DriveService()

    @property
    def tool_id(self) -> str:
        return "google_drive_search"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Search files across Google Drive by filename substring, full text, MIME type, or modification date."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name_contains": {"type": "string", "description": "Filename substring to match"},
                "full_text": {"type": "string", "description": "Full text keyword to match inside documents"},
                "mime_type": {"type": "string", "description": "MIME type filter"},
                "page_size": {"type": "integer", "description": "Max results to return", "default": 20},
            },
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            files = await self.service.search_files(
                name_contains=p.get("name_contains") or p.get("query"),
                full_text=p.get("full_text"),
                mime_type=p.get("mime_type"),
                page_size=p.get("page_size", 20),
            )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"files": files, "count": len(files)},
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class DriveReadTool(BaseTool):
    """Read a document or file's text content from Google Drive."""

    def __init__(self, service: DriveService | None = None) -> None:
        self.service = service or DriveService()

    @property
    def tool_id(self) -> str:
        return "google_drive_read"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Read textual content of a Google Drive file (automatically exports Google Docs and Sheets to text/csv)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Google Drive file ID"},
                "max_chars": {"type": "integer", "description": "Max characters to read", "default": 50000},
            },
            "required": ["file_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            res = await self.service.read_file(
                file_id=p.get("file_id", ""),
                max_chars=p.get("max_chars", 50000),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class DriveCreateFolderTool(BaseTool):
    """Create a folder in Google Drive."""

    def __init__(self, service: DriveService | None = None) -> None:
        self.service = service or DriveService()

    @property
    def tool_id(self) -> str:
        return "google_drive_create_folder"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Create a new folder in Google Drive with an optional parent folder."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the new folder"},
                "parent_id": {"type": "string", "description": "Optional parent folder ID"},
            },
            "required": ["name"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            folder = await self.service.create_folder(
                name=p.get("name", ""),
                parent_id=p.get("parent_id"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=folder)
        except Exception as e:
            return _format_google_error(self.name, e)


class DriveDeleteTool(BaseTool):
    """Trash or delete a file in Google Drive (destructive action)."""

    def __init__(self, service: DriveService | None = None) -> None:
        self.service = service or DriveService()

    @property
    def tool_id(self) -> str:
        return "google_drive_delete"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Move a file to trash or permanently delete it in Google Drive (requires confirmation)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID of the file to trash or delete"},
                "permanent": {"type": "boolean", "description": "Whether to permanently delete (default False)", "default": False},
            },
            "required": ["file_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            res = await self.service.delete_file(
                file_id=p.get("file_id", ""),
                permanent=p.get("permanent", False),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleDriveTool(BaseTool):
    """Unified Google Drive multi-action tool."""

    def __init__(self, service: DriveService | None = None) -> None:
        self.service = service or DriveService()

    @property
    def tool_id(self) -> str:
        return "google_drive"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Manage Google Drive: search files, list contents, read document text, create folders, upload, or move files."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "list", "read", "metadata", "create_folder", "create_file", "move", "rename", "delete"],
                    "description": "Drive action to execute",
                },
                "file_id": {"type": "string", "description": "File ID for read/metadata/move/rename/delete"},
                "name": {"type": "string", "description": "Name for folder creation, file creation, or rename"},
                "query": {"type": "string", "description": "Search query"},
                "parent_id": {"type": "string", "description": "Parent folder ID"},
                "content": {"type": "string", "description": "File text content for creation"},
                "mime_type": {"type": "string"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "search")

        try:
            if action == "search":
                files = await self.service.search_files(
                    name_contains=p.get("name") or p.get("query"),
                    mime_type=p.get("mime_type"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"files": files})

            elif action == "list":
                files = await self.service.list_files(folder_id=p.get("parent_id"))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"files": files})

            elif action == "read":
                res = await self.service.read_file(file_id=p.get("file_id", ""))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "metadata":
                res = await self.service.get_metadata(file_id=p.get("file_id", ""))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "create_folder":
                res = await self.service.create_folder(name=p.get("name", ""), parent_id=p.get("parent_id"))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "create_file":
                res = await self.service.create_file(
                    name=p.get("name", ""),
                    content=p.get("content", ""),
                    mime_type=p.get("mime_type", "text/plain"),
                    parent_id=p.get("parent_id"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "move":
                res = await self.service.move_file(
                    file_id=p.get("file_id", ""),
                    new_parent_id=p.get("parent_id", ""),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "rename":
                res = await self.service.rename_file(
                    file_id=p.get("file_id", ""),
                    new_name=p.get("name", ""),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "delete":
                res = await self.service.delete_file(file_id=p.get("file_id", ""))
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
