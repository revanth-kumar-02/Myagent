"""
integrations.google.calendar — Google Calendar Service Integration (V8)

Provides direct async integration with Google Calendar API v3:
- List calendars
- Get today's events / date range events
- Search events
- Create event (with validation of date, time, duration, timezone)
- Update event
- Delete event
- Check free/busy status
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, cast

import structlog

from integrations.google.client import GoogleWorkspaceClient
from integrations.google.errors import GoogleInvalidArgumentError

logger = structlog.get_logger(__name__)

CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"


class CalendarService:
    """Service wrapper for Google Calendar API v3."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def list_calendars(self, max_results: int = 50) -> list[dict[str, Any]]:
        """List user's calendars."""
        url = f"{CALENDAR_BASE_URL}/users/me/calendarList"
        data = await self.client.request("GET", url, params={"maxResults": max_results})
        items = data.get("items", [])
        return [
            {
                "id": c.get("id"),
                "summary": c.get("summary"),
                "description": c.get("description"),
                "timeZone": c.get("timeZone"),
                "primary": c.get("primary", False),
            }
            for c in items
        ]

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
        max_results: int = 50,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> list[dict[str, Any]]:
        """
        List or search events in a calendar within an optional time range.
        Times must be ISO 8601 strings (e.g. 2026-09-26T00:00:00Z).
        """
        url = f"{CALENDAR_BASE_URL}/calendars/{calendar_id}/events"
        params: dict[str, Any] = {
            "maxResults": max_results,
            "singleEvents": str(single_events).lower(),
        }
        if single_events and order_by:
            params["orderBy"] = order_by
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        if query:
            params["q"] = query

        data = await self.client.request("GET", url, params=params)
        items = data.get("items", [])
        return [self._format_event(e) for e in items]

    async def get_today_events(
        self, calendar_id: str = "primary", tz_offset_hours: float = 0.0
    ) -> list[dict[str, Any]]:
        """Retrieve all events occurring today in the specified or local timezone."""
        tz = timezone(timedelta(hours=tz_offset_hours))
        now = datetime.now(tz)
        start_of_day = datetime.combine(now.date(), time.min, tzinfo=tz).isoformat()
        end_of_day = datetime.combine(now.date(), time.max, tzinfo=tz).isoformat()
        return await self.list_events(
            calendar_id=calendar_id,
            time_min=start_of_day,
            time_max=end_of_day,
        )

    async def get_event(self, event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
        """Fetch details of a single calendar event."""
        if not event_id:
            raise GoogleInvalidArgumentError("event_id must not be empty.")
        url = f"{CALENDAR_BASE_URL}/calendars/{calendar_id}/events/{event_id}"
        data = await self.client.request("GET", url)
        return self._format_event(data)

    async def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str | None = None,
        duration_minutes: int | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
        time_zone: str = "UTC",
    ) -> dict[str, Any]:
        """
        Create a new event after validating date, time, timezone, and duration.
        start_time / end_time: ISO 8601 strings or YYYY-MM-DD for all-day events.
        """
        if not summary or not summary.strip():
            raise GoogleInvalidArgumentError("Event summary is required.")
        if not start_time:
            raise GoogleInvalidArgumentError("Event start_time is required.")

        start_body, end_body = self._validate_and_build_event_times(
            start_time, end_time, duration_minutes, time_zone
        )

        event_payload: dict[str, Any] = {
            "summary": summary.strip(),
            "start": start_body,
            "end": end_body,
        }
        if description:
            event_payload["description"] = description
        if location:
            event_payload["location"] = location
        if attendees:
            event_payload["attendees"] = [{"email": a.strip()} for a in attendees if a.strip()]

        url = f"{CALENDAR_BASE_URL}/calendars/{calendar_id}/events"
        data = await self.client.request("POST", url, json_data=event_payload)
        logger.info("calendar_event_created", event_id=data.get("id"), summary=summary)
        return self._format_event(data)

    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        summary: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        duration_minutes: int | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        time_zone: str = "UTC",
    ) -> dict[str, Any]:
        """Update an existing event."""
        if not event_id:
            raise GoogleInvalidArgumentError("event_id is required.")

        patch_payload: dict[str, Any] = {}
        if summary is not None:
            patch_payload["summary"] = summary
        if description is not None:
            patch_payload["description"] = description
        if location is not None:
            patch_payload["location"] = location
        if attendees is not None:
            patch_payload["attendees"] = [{"email": a.strip()} for a in attendees if a.strip()]

        if start_time is not None:
            start_body, end_body = self._validate_and_build_event_times(
                start_time, end_time, duration_minutes, time_zone
            )
            patch_payload["start"] = start_body
            if end_body:
                patch_payload["end"] = end_body
        elif end_time is not None:
            patch_payload["end"] = (
                {"date": end_time} if len(end_time) == 10 else {"dateTime": end_time, "timeZone": time_zone}
            )

        url = f"{CALENDAR_BASE_URL}/calendars/{calendar_id}/events/{event_id}"
        data = await self.client.request("PATCH", url, json_data=patch_payload)
        logger.info("calendar_event_updated", event_id=event_id)
        return self._format_event(data)

    async def delete_event(self, event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
        """Delete an event from the calendar (destructive action)."""
        if not event_id:
            raise GoogleInvalidArgumentError("event_id is required.")
        url = f"{CALENDAR_BASE_URL}/calendars/{calendar_id}/events/{event_id}"
        await self.client.request("DELETE", url)
        logger.info("calendar_event_deleted", event_id=event_id, calendar_id=calendar_id)
        return {"status": "deleted", "event_id": event_id, "calendar_id": calendar_id}

    async def check_freebusy(
        self,
        time_min: str,
        time_max: str,
        calendar_ids: list[str] | None = None,
        time_zone: str = "UTC",
    ) -> dict[str, Any]:
        """Query free/busy information for a list of calendars."""
        if not time_min or not time_max:
            raise GoogleInvalidArgumentError("time_min and time_max are required for freebusy check.")
        url = f"{CALENDAR_BASE_URL}/freeBusy"
        items = [{"id": cid} for cid in (calendar_ids or ["primary"])]
        payload = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": time_zone,
            "items": items,
        }
        res = await self.client.request("POST", url, json_data=payload)
        return cast(dict[str, Any], res if isinstance(res, dict) else {})

    def _validate_and_build_event_times(
        self,
        start_time: str,
        end_time: str | None,
        duration_minutes: int | None,
        time_zone: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Validates start/end strings and constructs Google event time objects."""
        # Check if all-day event (YYYY-MM-DD format)
        if len(start_time) == 10 and start_time.count("-") == 2:
            try:
                datetime.strptime(start_time, "%Y-%m-%d")
            except ValueError as ve:
                raise GoogleInvalidArgumentError(f"Invalid all-day start date '{start_time}': {ve}") from ve
            start_body = {"date": start_time}
            if end_time and len(end_time) == 10:
                end_body = {"date": end_time}
            else:
                end_body = {"date": start_time}
            return start_body, end_body

        # Parse ISO datetime
        try:
            parsed_start = datetime.fromisoformat(start_time)
        except Exception as e:
            raise GoogleInvalidArgumentError(
                f"Invalid start_time format '{start_time}'. Expected ISO 8601 (e.g. 2026-09-26T16:00:00Z): {e}"
            ) from e

        if end_time:
            try:
                parsed_end = datetime.fromisoformat(end_time)
            except Exception as e:
                raise GoogleInvalidArgumentError(
                    f"Invalid end_time format '{end_time}'. Expected ISO 8601: {e}"
                ) from e
            if parsed_end <= parsed_start:
                raise GoogleInvalidArgumentError("end_time must be strictly after start_time.")
            end_iso = parsed_end.isoformat()
        elif duration_minutes:
            if duration_minutes <= 0:
                raise GoogleInvalidArgumentError("duration_minutes must be a positive integer.")
            parsed_end = parsed_start + timedelta(minutes=duration_minutes)
            end_iso = parsed_end.isoformat()
        else:
            # Default 1 hour duration
            parsed_end = parsed_start + timedelta(hours=1)
            end_iso = parsed_end.isoformat()

        start_body = {"dateTime": parsed_start.isoformat(), "timeZone": time_zone}
        end_body = {"dateTime": end_iso, "timeZone": time_zone}
        return start_body, end_body

    def _format_event(self, data: dict[str, Any]) -> dict[str, Any]:
        """Formats raw calendar event object into a clean dictionary."""
        start = data.get("start", {})
        end = data.get("end", {})
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "htmlLink": data.get("htmlLink"),
            "summary": data.get("summary", "(No Title)"),
            "description": data.get("description"),
            "location": data.get("location"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "organizer": data.get("organizer", {}).get("email"),
            "attendees": [
                {"email": a.get("email"), "responseStatus": a.get("responseStatus")}
                for a in data.get("attendees", [])
            ],
            "hangoutLink": data.get("hangoutLink"),
        }
