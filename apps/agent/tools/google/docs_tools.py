"""
tools.google.docs_tools — Google Docs Agent Tools (V8)

Provides granular tools (google_docs_read, google_docs_create, google_docs_update)
and unified tool (google_docs).
"""

from __future__ import annotations

from typing import Any

from integrations.google.docs import DocsService
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
        error=f"Docs operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class DocsReadTool(BaseTool):
    """Read full text content from a Google Document."""

    def __init__(self, service: DocsService | None = None) -> None:
        self.service = service or DocsService()

    @property
    def tool_id(self) -> str:
        return "google_docs_read"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Read text content and structure from a Google Document by document_id."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Google Docs document ID"},
            },
            "required": ["document_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            doc = await self.service.read_document_text(document_id=p.get("document_id", ""))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=doc)
        except Exception as e:
            return _format_google_error(self.name, e)


class DocsCreateTool(BaseTool):
    """Create a new Google Document."""

    def __init__(self, service: DocsService | None = None) -> None:
        self.service = service or DocsService()

    @property
    def tool_id(self) -> str:
        return "google_docs_create"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Create a new blank Google Document with the given title."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title for the new Google Document"},
            },
            "required": ["title"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            doc = await self.service.create_document(title=p.get("title", ""))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=doc)
        except Exception as e:
            return _format_google_error(self.name, e)


class DocsUpdateTool(BaseTool):
    """Update or append content to a Google Document."""

    def __init__(self, service: DocsService | None = None) -> None:
        self.service = service or DocsService()

    @property
    def tool_id(self) -> str:
        return "google_docs_update"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Append or insert text into an existing Google Document."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Google Docs document ID"},
                "text": {"type": "string", "description": "Text content to insert or append"},
                "index": {"type": "integer", "description": "Optional index to insert at (if omitted, appends to end)"},
            },
            "required": ["document_id", "text"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            doc_id = p.get("document_id", "")
            text = p.get("text", "")
            index = p.get("index")

            if index is not None and index >= 1:
                res = await self.service.insert_text(document_id=doc_id, text=text, index=index)
            else:
                res = await self.service.append_text(document_id=doc_id, text=text)

            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleDocsTool(BaseTool):
    """Unified Google Docs multi-action tool."""

    def __init__(self, service: DocsService | None = None) -> None:
        self.service = service or DocsService()

    @property
    def tool_id(self) -> str:
        return "google_docs"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Interact with Google Docs: read text, create new documents, append or insert text."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "create", "append", "insert"],
                    "description": "Docs action to perform",
                },
                "document_id": {"type": "string", "description": "Document ID for read/append/insert"},
                "title": {"type": "string", "description": "Title for document creation"},
                "text": {"type": "string", "description": "Text content to append or insert"},
                "index": {"type": "integer", "description": "Index for insert action"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "read")
        doc_id = p.get("document_id", "")

        try:
            if action == "read":
                res = await self.service.read_document_text(document_id=doc_id)
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "create":
                res = await self.service.create_document(title=p.get("title", ""))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "append":
                res = await self.service.append_text(document_id=doc_id, text=p.get("text", ""))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "insert":
                res = await self.service.insert_text(
                    document_id=doc_id,
                    text=p.get("text", ""),
                    index=p.get("index", 1),
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
