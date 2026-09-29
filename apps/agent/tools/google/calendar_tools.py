"""
tools.google.calendar_tools — Google Calendar Agent Tools (V8)

Provides granular tools (google_calendar_list_events, google_calendar_create_event,
google_calendar_update_event, google_calendar_delete_event) and unified (google_calendar).
"""

from __future__ import annotations

from typing import Any

from integrations.google.calendar import CalendarService
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
        error=f"Calendar operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class CalendarListEventsTool(BaseTool):
    """List or search events on a Google Calendar."""

    def __init__(self, service: CalendarService | None = None) -> None:
        self.service = service or CalendarService()

    @property
    def tool_id(self) -> str:
        return "google_calendar_list_events"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "List or search events in the user's Google Calendar with optional time range or search query."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (defaults to 'primary')", "default": "primary"},
                "time_min": {"type": "string", "description": "ISO 8601 start time (e.g. '2026-09-26T00:00:00Z')"},
                "time_max": {"type": "string", "description": "ISO 8601 end time"},
                "query": {"type": "string", "description": "Free text search query"},
                "max_results": {"type": "integer", "description": "Max events to return", "default": 20},
            },
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            events = await self.service.list_events(
                calendar_id=p.get("calendar_id", "primary"),
                time_min=p.get("time_min"),
                time_max=p.get("time_max"),
                query=p.get("query"),
                max_results=p.get("max_results", 20),
            )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"events": events, "count": len(events)},
            )
        except Exception as e:
            return _format_google_error(self.name, e)


class CalendarCreateEventTool(BaseTool):
    """Create a new event on Google Calendar."""

    def __init__(self, service: CalendarService | None = None) -> None:
        self.service = service or CalendarService()

    @property
    def tool_id(self) -> str:
        return "google_calendar_create_event"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Create a new event on Google Calendar. Requires summary and start_time."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Title/summary of the meeting or event"},
                "start_time": {"type": "string", "description": "ISO 8601 start datetime or YYYY-MM-DD"},
                "end_time": {"type": "string", "description": "ISO 8601 end datetime or YYYY-MM-DD"},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes if end_time not provided"},
                "description": {"type": "string", "description": "Event description or agenda notes"},
                "location": {"type": "string", "description": "Meeting location or link"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee email addresses"},
                "calendar_id": {"type": "string", "default": "primary"},
                "time_zone": {"type": "string", "default": "UTC"},
            },
            "required": ["summary", "start_time"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            ev = await self.service.create_event(
                summary=p.get("summary", ""),
                start_time=p.get("start_time", ""),
                end_time=p.get("end_time"),
                duration_minutes=p.get("duration_minutes"),
                description=p.get("description"),
                location=p.get("location"),
                attendees=p.get("attendees"),
                calendar_id=p.get("calendar_id", "primary"),
                time_zone=p.get("time_zone", "UTC"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=ev)
        except Exception as e:
            return _format_google_error(self.name, e)


class CalendarUpdateEventTool(BaseTool):
    """Update an existing event on Google Calendar."""

    def __init__(self, service: CalendarService | None = None) -> None:
        self.service = service or CalendarService()

    @property
    def tool_id(self) -> str:
        return "google_calendar_update_event"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Update an existing Google Calendar event's time, title, description, or attendees."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID of the event to update"},
                "calendar_id": {"type": "string", "default": "primary"},
                "summary": {"type": "string", "description": "New event title"},
                "start_time": {"type": "string", "description": "New ISO start time"},
                "end_time": {"type": "string", "description": "New ISO end time"},
                "duration_minutes": {"type": "integer", "description": "New duration in minutes"},
                "description": {"type": "string", "description": "New description"},
                "location": {"type": "string", "description": "New location"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["event_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            ev = await self.service.update_event(
                event_id=p.get("event_id", ""),
                calendar_id=p.get("calendar_id", "primary"),
                summary=p.get("summary"),
                start_time=p.get("start_time"),
                end_time=p.get("end_time"),
                duration_minutes=p.get("duration_minutes"),
                description=p.get("description"),
                location=p.get("location"),
                attendees=p.get("attendees"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=ev)
        except Exception as e:
            return _format_google_error(self.name, e)


class CalendarDeleteEventTool(BaseTool):
    """Delete an event from Google Calendar (destructive)."""

    def __init__(self, service: CalendarService | None = None) -> None:
        self.service = service or CalendarService()

    @property
    def tool_id(self) -> str:
        return "google_calendar_delete_event"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Delete an event from Google Calendar (requires confirmation)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID of the event to delete"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["event_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            res = await self.service.delete_event(
                event_id=p.get("event_id", ""),
                calendar_id=p.get("calendar_id", "primary"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleCalendarTool(BaseTool):
    """Unified Google Calendar multi-action tool."""

    def __init__(self, service: CalendarService | None = None) -> None:
        self.service = service or CalendarService()

    @property
    def tool_id(self) -> str:
        return "google_calendar"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return (
            "Interact with Google Calendar: list events, get today's events, "
            "create events, update events, delete events, or check free/busy."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "today", "get", "create", "update", "delete", "freebusy"],
                    "description": "Calendar action to perform",
                },
                "calendar_id": {"type": "string", "default": "primary"},
                "event_id": {"type": "string", "description": "Event ID for get/update/delete"},
                "summary": {"type": "string", "description": "Event summary for create/update"},
                "start_time": {"type": "string", "description": "Start ISO datetime"},
                "end_time": {"type": "string", "description": "End ISO datetime"},
                "duration_minutes": {"type": "integer"},
                "query": {"type": "string", "description": "Search query for list"},
                "time_min": {"type": "string"},
                "time_max": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "list")

        try:
            if action == "list":
                events = await self.service.list_events(
                    calendar_id=p.get("calendar_id", "primary"),
                    time_min=p.get("time_min"),
                    time_max=p.get("time_max"),
                    query=p.get("query"),
                    max_results=p.get("max_results", 20),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"events": events})

            elif action == "today":
                events = await self.service.get_today_events(calendar_id=p.get("calendar_id", "primary"))
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"events": events})

            elif action == "get":
                ev = await self.service.get_event(
                    event_id=p.get("event_id", ""),
                    calendar_id=p.get("calendar_id", "primary"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=ev)

            elif action == "create":
                ev = await self.service.create_event(
                    summary=p.get("summary", ""),
                    start_time=p.get("start_time", ""),
                    end_time=p.get("end_time"),
                    duration_minutes=p.get("duration_minutes"),
                    description=p.get("description"),
                    location=p.get("location"),
                    attendees=p.get("attendees"),
                    calendar_id=p.get("calendar_id", "primary"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=ev)

            elif action == "update":
                ev = await self.service.update_event(
                    event_id=p.get("event_id", ""),
                    calendar_id=p.get("calendar_id", "primary"),
                    summary=p.get("summary"),
                    start_time=p.get("start_time"),
                    end_time=p.get("end_time"),
                    duration_minutes=p.get("duration_minutes"),
                    description=p.get("description"),
                    location=p.get("location"),
                    attendees=p.get("attendees"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=ev)

            elif action == "delete":
                res = await self.service.delete_event(
                    event_id=p.get("event_id", ""),
                    calendar_id=p.get("calendar_id", "primary"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            elif action == "freebusy":
                res = await self.service.check_freebusy(
                    time_min=p.get("time_min", ""),
                    time_max=p.get("time_max", ""),
                    calendar_ids=[p.get("calendar_id", "primary")],
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
