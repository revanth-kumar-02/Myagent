"""
tools.google.gmail_tools — Google Gmail Agent Tools (V8)

Provides both granular tools (google_gmail_search, google_gmail_read, google_gmail_send, etc.)
and a unified tool (google_gmail) registered with Kora's Tool Registry.
"""

from __future__ import annotations

from typing import Any

from integrations.google.errors import GoogleWorkspaceError
from integrations.google.gmail import GmailService
from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult, ToolStatus


def _format_google_error(tool_name: str, err: Exception) -> ToolResult:
    """Format exceptions into clean, structured ToolResult without leaking tokens."""
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
        error=f"Gmail operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class GmailSearchTool(BaseTool):
    """Search messages in Gmail."""

    def __init__(self, service: GmailService | None = None) -> None:
        self.service = service or GmailService()

    @property
    def tool_id(self) -> str:
        return "google_gmail_search"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Search emails in user's Gmail using search queries (e.g. from:google, subject:hackathon, has:attachment)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query string (e.g. 'hackathon', 'from:google')"},
                "max_results": {"type": "integer", "description": "Max results to return (default 10)", "default": 10},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            results = await self.service.search_emails(
                query=p.get("query", ""),
                max_results=p.get("max_results", 10),
            )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"messages": results, "count": len(results)},
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class GmailReadTool(BaseTool):
    """Read a specific email or thread content by message_id."""

    def __init__(self, service: GmailService | None = None) -> None:
        self.service = service or GmailService()

    @property
    def tool_id(self) -> str:
        return "google_gmail_read"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Retrieve and read complete email content and metadata by Gmail message_id."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "The unique Gmail message ID"},
            },
            "required": ["message_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            msg = await self.service.read_email(message_id=p.get("message_id", ""))
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=msg,
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class GmailDraftTool(BaseTool):
    """Create an email draft in Gmail."""

    def __init__(self, service: GmailService | None = None) -> None:
        self.service = service or GmailService()

    @property
    def tool_id(self) -> str:
        return "google_gmail_draft"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Create a new draft email in Gmail without sending it."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain text body content of the email"},
                "thread_id": {"type": "string", "description": "Optional thread ID to reply within"},
            },
            "required": ["to", "subject", "body"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            draft = await self.service.create_draft(
                to=p.get("to", ""),
                subject=p.get("subject", ""),
                body=p.get("body", ""),
                thread_id=p.get("thread_id"),
            )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=draft,
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class GmailSendTool(BaseTool):
    """Send an email directly via Gmail (destructive action)."""

    def __init__(self, service: GmailService | None = None) -> None:
        self.service = service or GmailService()

    @property
    def tool_id(self) -> str:
        return "google_gmail_send"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Send an email directly from the user's Gmail account (requires confirmation)."

    @property
    def permission_level(self) -> PermissionLevel:
        # High impact action requires explicit user permission
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Body content of the email"},
                "thread_id": {"type": "string", "description": "Optional thread ID for replying"},
            },
            "required": ["to", "subject", "body"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            sent = await self.service.send_email(
                to=p.get("to", ""),
                subject=p.get("subject", ""),
                body=p.get("body", ""),
                thread_id=p.get("thread_id"),
            )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=sent,
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleGmailTool(BaseTool):
    """Unified Gmail multi-action dispatcher tool."""

    def __init__(self, service: GmailService | None = None) -> None:
        self.service = service or GmailService()

    @property
    def tool_id(self) -> str:
        return "google_gmail"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return (
            "Interact with Gmail: search emails, read messages, list recent, "
            "create drafts, send emails, or modify labels."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "read", "list", "draft", "send", "modify_labels"],
                    "description": "The Gmail action to perform",
                },
                "query": {"type": "string", "description": "Search query for 'search'"},
                "message_id": {"type": "string", "description": "Message ID for 'read' or 'modify_labels'"},
                "to": {"type": "string", "description": "Recipient email for 'draft' or 'send'"},
                "subject": {"type": "string", "description": "Subject for 'draft' or 'send'"},
                "body": {"type": "string", "description": "Body for 'draft' or 'send'"},
                "thread_id": {"type": "string", "description": "Thread ID for replies"},
                "max_results": {"type": "integer", "description": "Max results for 'list' or 'search'"},
                "add_labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add"},
                "remove_labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to remove"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "search")

        try:
            if action == "search":
                res = await self.service.search_emails(
                    query=p.get("query", ""),
                    max_results=p.get("max_results", 10),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"messages": res})

            elif action == "read":
                res = await self.service.read_email(message_id=p.get("message_id", ""))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "list":
                res = await self.service.list_recent_emails(
                    max_results=p.get("max_results", 10),
                    label_ids=p.get("label_ids"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"messages": res})

            elif action == "draft":
                res = await self.service.create_draft(
                    to=p.get("to", ""),
                    subject=p.get("subject", ""),
                    body=p.get("body", ""),
                    thread_id=p.get("thread_id"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "send":
                res = await self.service.send_email(
                    to=p.get("to", ""),
                    subject=p.get("subject", ""),
                    body=p.get("body", ""),
                    thread_id=p.get("thread_id"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "modify_labels":
                res = await self.service.modify_labels(
                    message_id=p.get("message_id", ""),
                    add_labels=p.get("add_labels"),
                    remove_labels=p.get("remove_labels"),
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
