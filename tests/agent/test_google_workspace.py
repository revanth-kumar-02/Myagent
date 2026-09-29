"""
tests.agent.test_google_workspace — Comprehensive Test Suite for Google Workspace Tools (V8 / Phase 2)

Tests:
1. Gmail: search, read, draft, send
2. Calendar: list events, create event, update event, delete event
3. Drive: search, metadata, folder creation, delete/trash
4. Tasks: list, create, complete
5. Docs: read, create, update (append/insert)
6. Sheets: read, write, append
7. Resilient error handling:
   - Expired token & refresh
   - Permission denied (403)
   - Not found (404)
   - Rate limit (429)
   - Malformed input & validation
   - Token secrecy (no credentials leaked)
8. Tool registry discovery & OpenAI function calling schema export
9. Destructive actions confirmation gate (PermissionLevel.HIGH_IMPACT_ACTION)
10. Natural language intent analysis and planner mapping
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.intent_analyzer import IntentAnalyzer
from core.planner import Planner
from core.types import ChatRequest, IntentType
from integrations.google.auth import GoogleAuthManager
from integrations.google.calendar import CalendarService
from integrations.google.client import GoogleWorkspaceClient
from integrations.google.docs import DocsService
from integrations.google.drive import DriveService
from integrations.google.errors import (
    GoogleAuthRequiredError,
    GoogleNotFoundError,
    GooglePermissionDeniedError,
    GoogleRateLimitedError,
    GoogleTokenExpiredError,
    GoogleWorkspaceError,
)
from integrations.google.gmail import GmailService
from integrations.google.sheets import SheetsService
from integrations.google.tasks import TasksService
from permissions.gate import PermissionDeniedError, PermissionGate
from tools.base import ToolValidationError
from tools.google import (
    CalendarCreateEventTool,
    CalendarDeleteEventTool,
    CalendarListEventsTool,
    CalendarUpdateEventTool,
    DocsCreateTool,
    DocsReadTool,
    DocsUpdateTool,
    DriveCreateFolderTool,
    DriveDeleteTool,
    DriveReadTool,
    DriveSearchTool,
    GmailDraftTool,
    GmailReadTool,
    GmailSearchTool,
    GmailSendTool,
    GoogleCalendarTool,
    GoogleDocsTool,
    GoogleDriveTool,
    GoogleGmailTool,
    GoogleSheetsTool,
    GoogleTasksTool,
    SheetsAppendTool,
    SheetsReadTool,
    SheetsWriteTool,
    TasksCompleteTool,
    TasksCreateTool,
    TasksListTool,
)
from tools.registry import ToolRegistry, build_default_registry
from tools.types import PermissionLevel, ToolCategory, ToolStatus


# ─────────────────────────────────────────────────────────────────────────────
# 1. GMAIL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestGmailTools:

    @pytest.mark.asyncio
    async def test_gmail_search(self) -> None:
        mock_service = MagicMock(spec=GmailService)
        mock_service.search_emails = AsyncMock(return_value=[
            {"id": "msg_001", "subject": "GDG Hackathon", "from": "hackathon@google.com", "snippet": "Welcome!"}
        ])
        tool = GmailSearchTool(service=mock_service)
        result = await tool.run({"query": "hackathon"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["count"] == 1
        assert result.output["messages"][0]["id"] == "msg_001"
        mock_service.search_emails.assert_awaited_once_with(query="hackathon", max_results=10)

    @pytest.mark.asyncio
    async def test_gmail_read(self) -> None:
        mock_service = MagicMock(spec=GmailService)
        mock_service.read_email = AsyncMock(return_value={
            "id": "msg_001",
            "subject": "GDG Hackathon",
            "from": "hackathon@google.com",
            "body": "Your project is selected.",
        })
        tool = GmailReadTool(service=mock_service)
        result = await tool.run({"message_id": "msg_001"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["subject"] == "GDG Hackathon"
        assert "project is selected" in result.output["body"]

    @pytest.mark.asyncio
    async def test_gmail_draft(self) -> None:
        mock_service = MagicMock(spec=GmailService)
        mock_service.create_draft = AsyncMock(return_value={
            "draft_id": "draft_123",
            "message_id": "msg_draft",
        })
        tool = GmailDraftTool(service=mock_service)
        result = await tool.run({
            "to": "teammate@example.com",
            "subject": "Project Ready",
            "body": "The Kora Google integration is done!",
        })

        assert result.status == ToolStatus.SUCCESS
        assert result.output["draft_id"] == "draft_123"
        assert tool.permission_level == PermissionLevel.LOW_RISK_WRITE

    @pytest.mark.asyncio
    async def test_gmail_send_requires_high_impact_permission(self) -> None:
        tool = GmailSendTool()
        assert tool.permission_level == PermissionLevel.HIGH_IMPACT_ACTION

    @pytest.mark.asyncio
    async def test_gmail_send_execution(self) -> None:
        mock_service = MagicMock(spec=GmailService)
        mock_service.send_email = AsyncMock(return_value={
            "id": "sent_001",
            "status": "SENT",
        })
        tool = GmailSendTool(service=mock_service)
        result = await tool.run({
            "to": "teammate@example.com",
            "subject": "Shipped",
            "body": "Phase 2 is live.",
        })

        assert result.status == ToolStatus.SUCCESS
        assert result.output["status"] == "SENT"


# ─────────────────────────────────────────────────────────────────────────────
# 2. CALENDAR TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestCalendarTools:

    @pytest.mark.asyncio
    async def test_calendar_list_events(self) -> None:
        mock_service = MagicMock(spec=CalendarService)
        mock_service.list_events = AsyncMock(return_value=[
            {"id": "ev_001", "summary": "Kora Demo", "start": "2026-09-26T16:00:00Z"}
        ])
        tool = CalendarListEventsTool(service=mock_service)
        result = await tool.run({})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["count"] == 1
        assert result.output["events"][0]["summary"] == "Kora Demo"

    @pytest.mark.asyncio
    async def test_calendar_create_event(self) -> None:
        mock_service = MagicMock(spec=CalendarService)
        mock_service.create_event = AsyncMock(return_value={
            "id": "ev_new",
            "summary": "Hackathon Meeting",
            "start": "2026-09-27T16:00:00Z",
            "end": "2026-09-27T17:00:00Z",
        })
        tool = CalendarCreateEventTool(service=mock_service)
        result = await tool.run({
            "summary": "Hackathon Meeting",
            "start_time": "2026-09-27T16:00:00Z",
            "duration_minutes": 60,
        })

        assert result.status == ToolStatus.SUCCESS
        assert result.output["id"] == "ev_new"

    @pytest.mark.asyncio
    async def test_calendar_update_event(self) -> None:
        mock_service = MagicMock(spec=CalendarService)
        mock_service.update_event = AsyncMock(return_value={
            "id": "ev_001",
            "summary": "Rescheduled Demo",
            "start": "2026-09-27T18:00:00Z",
        })
        tool = CalendarUpdateEventTool(service=mock_service)
        result = await tool.run({
            "event_id": "ev_001",
            "summary": "Rescheduled Demo",
            "start_time": "2026-09-27T18:00:00Z",
        })

        assert result.status == ToolStatus.SUCCESS
        assert result.output["summary"] == "Rescheduled Demo"

    @pytest.mark.asyncio
    async def test_calendar_delete_event_destructive(self) -> None:
        tool = CalendarDeleteEventTool()
        assert tool.permission_level == PermissionLevel.HIGH_IMPACT_ACTION

        mock_service = MagicMock(spec=CalendarService)
        mock_service.delete_event = AsyncMock(return_value={"status": "deleted", "event_id": "ev_001"})
        tool = CalendarDeleteEventTool(service=mock_service)
        result = await tool.run({"event_id": "ev_001"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["status"] == "deleted"


# ─────────────────────────────────────────────────────────────────────────────
# 3. DRIVE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestDriveTools:

    @pytest.mark.asyncio
    async def test_drive_search(self) -> None:
        mock_service = MagicMock(spec=DriveService)
        mock_service.search_files = AsyncMock(return_value=[
            {"id": "file_doc", "name": "Kora Architecture", "mimeType": "application/vnd.google-apps.document"}
        ])
        tool = DriveSearchTool(service=mock_service)
        result = await tool.run({"name_contains": "Architecture"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["count"] == 1
        assert result.output["files"][0]["name"] == "Kora Architecture"

    @pytest.mark.asyncio
    async def test_drive_read_document_export(self) -> None:
        mock_service = MagicMock(spec=DriveService)
        mock_service.read_file = AsyncMock(return_value={
            "file_id": "file_doc",
            "name": "Kora Architecture",
            "mimeType": "application/vnd.google-apps.document",
            "exportedAs": "text/plain",
            "content": "# Kora Architecture\nAgent + Tool Registry.",
        })
        tool = DriveReadTool(service=mock_service)
        result = await tool.run({"file_id": "file_doc"})

        assert result.status == ToolStatus.SUCCESS
        assert "Agent + Tool Registry" in result.output["content"]

    @pytest.mark.asyncio
    async def test_drive_create_folder(self) -> None:
        mock_service = MagicMock(spec=DriveService)
        mock_service.create_folder = AsyncMock(return_value={
            "id": "fld_123",
            "name": "Hackathon",
            "mimeType": "application/vnd.google-apps.folder",
        })
        tool = DriveCreateFolderTool(service=mock_service)
        result = await tool.run({"name": "Hackathon"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["id"] == "fld_123"

    @pytest.mark.asyncio
    async def test_drive_delete_file_destructive(self) -> None:
        tool = DriveDeleteTool()
        assert tool.permission_level == PermissionLevel.HIGH_IMPACT_ACTION

        mock_service = MagicMock(spec=DriveService)
        mock_service.delete_file = AsyncMock(return_value={"status": "trashed", "file_id": "file_001"})
        tool = DriveDeleteTool(service=mock_service)
        result = await tool.run({"file_id": "file_001"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["status"] == "trashed"


# ─────────────────────────────────────────────────────────────────────────────
# 4. TASKS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestTasksTools:

    @pytest.mark.asyncio
    async def test_tasks_list(self) -> None:
        mock_service = MagicMock(spec=TasksService)
        mock_service.list_tasks = AsyncMock(return_value=[
            {"id": "tsk_01", "title": "Finish Kora Google integration", "status": "needsAction"}
        ])
        tool = TasksListTool(service=mock_service)
        result = await tool.run({})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["count"] == 1
        assert result.output["tasks"][0]["title"] == "Finish Kora Google integration"

    @pytest.mark.asyncio
    async def test_tasks_create(self) -> None:
        mock_service = MagicMock(spec=TasksService)
        mock_service.create_task = AsyncMock(return_value={
            "id": "tsk_new",
            "title": "Build Phase 2",
            "status": "needsAction",
        })
        tool = TasksCreateTool(service=mock_service)
        result = await tool.run({"title": "Build Phase 2", "notes": "Implement Google tools"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["id"] == "tsk_new"

    @pytest.mark.asyncio
    async def test_tasks_complete(self) -> None:
        mock_service = MagicMock(spec=TasksService)
        mock_service.complete_task = AsyncMock(return_value={
            "id": "tsk_01",
            "status": "completed",
        })
        tool = TasksCompleteTool(service=mock_service)
        result = await tool.run({"task_id": "tsk_01"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["status"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
# 5. DOCS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestDocsTools:

    @pytest.mark.asyncio
    async def test_docs_create(self) -> None:
        mock_service = MagicMock(spec=DocsService)
        mock_service.create_document = AsyncMock(return_value={
            "document_id": "doc_new_01",
            "title": "Kora Roadmap",
        })
        tool = DocsCreateTool(service=mock_service)
        result = await tool.run({"title": "Kora Roadmap"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["document_id"] == "doc_new_01"

    @pytest.mark.asyncio
    async def test_docs_read(self) -> None:
        mock_service = MagicMock(spec=DocsService)
        mock_service.read_document_text = AsyncMock(return_value={
            "document_id": "doc_01",
            "title": "Kora Roadmap",
            "content": "Phase 1: Local tools.\nPhase 2: Google Workspace.",
        })
        tool = DocsReadTool(service=mock_service)
        result = await tool.run({"document_id": "doc_01"})

        assert result.status == ToolStatus.SUCCESS
        assert "Phase 2: Google Workspace" in result.output["content"]

    @pytest.mark.asyncio
    async def test_docs_update_append(self) -> None:
        mock_service = MagicMock(spec=DocsService)
        mock_service.append_text = AsyncMock(return_value={
            "document_id": "doc_01",
            "replies": [{"insertText": {}}],
        })
        tool = DocsUpdateTool(service=mock_service)
        result = await tool.run({
            "document_id": "doc_01",
            "text": "Phase 2 is completed!",
        })

        assert result.status == ToolStatus.SUCCESS
        mock_service.append_text.assert_awaited_once_with(
            document_id="doc_01", text="Phase 2 is completed!"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. SHEETS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestSheetsTools:

    @pytest.mark.asyncio
    async def test_sheets_read(self) -> None:
        mock_service = MagicMock(spec=SheetsService)
        mock_service.read_range = AsyncMock(return_value={
            "spreadsheetId": "sheet_123",
            "range": "Sheet1!A1:D5",
            "values": [["Name", "Role"], ["Alice", "Lead"], ["Bob", "Engineer"]],
        })
        tool = SheetsReadTool(service=mock_service)
        result = await tool.run({
            "spreadsheet_id": "sheet_123",
            "range_notation": "Sheet1!A1:D5",
        })

        assert result.status == ToolStatus.SUCCESS
        assert len(result.output["values"]) == 3

    @pytest.mark.asyncio
    async def test_sheets_append(self) -> None:
        mock_service = MagicMock(spec=SheetsService)
        mock_service.append_rows = AsyncMock(return_value={
            "spreadsheetId": "sheet_123",
            "updatedRows": 1,
            "updatedCells": 2,
        })
        tool = SheetsAppendTool(service=mock_service)
        result = await tool.run({
            "spreadsheet_id": "sheet_123",
            "range_notation": "Sheet1!A:B",
            "values": [["Charlie", "Designer"]],
        })

        assert result.status == ToolStatus.SUCCESS
        assert result.output["updatedRows"] == 1

    @pytest.mark.asyncio
    async def test_sheets_write_is_high_impact(self) -> None:
        tool = SheetsWriteTool()
        assert tool.permission_level == PermissionLevel.HIGH_IMPACT_ACTION


# ─────────────────────────────────────────────────────────────────────────────
# 7. STRUCTURED ERRORS & TOKEN PROTECTION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestGoogleErrorsAndSecurity:

    @pytest.mark.asyncio
    async def test_auth_required_error_translation(self) -> None:
        mock_service = MagicMock(spec=GmailService)
        mock_service.search_emails = AsyncMock(
            side_effect=GoogleAuthRequiredError("Google authorization is required to access Gmail.")
        )
        tool = GmailSearchTool(service=mock_service)
        result = await tool.run({"query": "test"})

        assert result.status == ToolStatus.ERROR
        assert result.output["error_code"] == "GOOGLE_AUTH_REQUIRED"
        assert result.error is not None
        assert "authorization is required" in result.error
        # Ensure no secret tokens leaked
        assert "access_token" not in result.error
        assert "refresh_token" not in result.error

    @pytest.mark.asyncio
    async def test_token_expired_error_translation(self) -> None:
        mock_service = MagicMock(spec=CalendarService)
        mock_service.list_events = AsyncMock(
            side_effect=GoogleTokenExpiredError("Google credentials expired.")
        )
        tool = CalendarListEventsTool(service=mock_service)
        result = await tool.run({})

        assert result.status == ToolStatus.ERROR
        assert result.output["error_code"] == "GOOGLE_TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_permission_denied_error_translation(self) -> None:
        mock_service = MagicMock(spec=DriveService)
        mock_service.search_files = AsyncMock(
            side_effect=GooglePermissionDeniedError("Google Drive permission denied.")
        )
        tool = DriveSearchTool(service=mock_service)
        result = await tool.run({})

        assert result.status == ToolStatus.ERROR
        assert result.output["error_code"] == "GOOGLE_PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_not_found_error_translation(self) -> None:
        mock_service = MagicMock(spec=DocsService)
        mock_service.read_document_text = AsyncMock(
            side_effect=GoogleNotFoundError("Document not found.")
        )
        tool = DocsReadTool(service=mock_service)
        result = await tool.run({"document_id": "nonexistent"})

        assert result.status == ToolStatus.ERROR
        assert result.output["error_code"] == "GOOGLE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_rate_limited_error_translation(self) -> None:
        mock_service = MagicMock(spec=SheetsService)
        mock_service.read_range = AsyncMock(
            side_effect=GoogleRateLimitedError("Google Sheets rate limit exceeded.")
        )
        tool = SheetsReadTool(service=mock_service)
        result = await tool.run({"spreadsheet_id": "s1", "range_notation": "A1"})

        assert result.status == ToolStatus.ERROR
        assert result.output["error_code"] == "GOOGLE_RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_malformed_input_validation(self) -> None:
        tool = GmailSearchTool()
        # Missing required parameter 'query'
        result = await tool.run({})
        assert result.status == ToolStatus.ERROR
        assert result.error is not None
        assert "Missing required parameter" in result.error


# ─────────────────────────────────────────────────────────────────────────────
# 8. TOOL REGISTRY & FUNCTION-CALLING SCHEMA EXPORT
# ─────────────────────────────────────────────────────────────────────────────

class TestGoogleToolRegistry:

    def test_all_google_tools_registered(self) -> None:
        reg = build_default_registry()
        workspace_tools = reg.get_by_category(ToolCategory.WORKSPACE)

        expected_tools = [
            "google_gmail",
            "google_gmail_search",
            "google_gmail_read",
            "google_gmail_draft",
            "google_gmail_send",
            "google_calendar",
            "google_calendar_list_events",
            "google_calendar_create_event",
            "google_calendar_update_event",
            "google_calendar_delete_event",
            "google_drive",
            "google_drive_search",
            "google_drive_read",
            "google_drive_create_folder",
            "google_drive_delete",
            "google_tasks",
            "google_tasks_list",
            "google_tasks_create",
            "google_tasks_complete",
            "google_docs",
            "google_docs_read",
            "google_docs_create",
            "google_docs_update",
            "google_sheets",
            "google_sheets_read",
            "google_sheets_write",
            "google_sheets_append",
        ]

        registered_names = {t.name for t in workspace_tools}
        for name in expected_tools:
            assert name in registered_names, f"Expected {name} to be registered in ToolRegistry"

    def test_schema_export_for_llm(self) -> None:
        reg = build_default_registry()
        schemas = reg.to_schema()

        gmail_schema = next((s for s in schemas if s["name"] == "google_gmail_search"), None)
        assert gmail_schema is not None
        assert "parameters" in gmail_schema
        assert "query" in gmail_schema["parameters"]["properties"]
        assert "query" in gmail_schema["parameters"]["required"]


# ─────────────────────────────────────────────────────────────────────────────
# 9. CONFIRMATION GATE FOR DESTRUCTIVE ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestDestructiveActionsGate:

    @pytest.mark.asyncio
    async def test_permission_gate_intercepts_destructive_tools(self) -> None:
        gate = PermissionGate()
        send_tool = GmailSendTool()

        # Without interactive client / user grant, checking high impact tool raises PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await gate.check(send_tool)

        # After grant for session, passes through
        gate.grant_for_session("google_gmail_send")
        await gate.check(send_tool)  # Should not raise

    @pytest.mark.asyncio
    async def test_calendar_delete_blocked_by_default(self) -> None:
        gate = PermissionGate()
        cal_del = CalendarDeleteEventTool()
        with pytest.raises(PermissionDeniedError):
            await gate.check(cal_del)


# ─────────────────────────────────────────────────────────────────────────────
# 10. INTENT ANALYZER & PLANNER INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentAndPlannerIntegration:

    def test_intent_analyzer_classifies_google_queries(self) -> None:
        analyzer = IntentAnalyzer()

        queries = [
            "Find the email from Google about the hackathon.",
            "What's on my calendar today?",
            "Find my Kora documentation in Drive.",
            "Add 'finish Kora Google integration' to my tasks.",
            "Create a document called Kora Roadmap.",
            "Read rows A1:D20.",
        ]

        for q in queries:
            intent, _ = analyzer.analyze(q)
            assert intent == IntentType.TOOL_ACTION, f"Query '{q}' should be classified as TOOL_ACTION"

    @pytest.mark.asyncio
    async def test_planner_creates_correct_google_tool_steps(self) -> None:
        planner = Planner()
        sid = uuid.uuid4()

        req_email = ChatRequest(message="Find the email from Google about the hackathon.", session_id=sid, project_id=None)
        plan_email = await planner.plan(req_email)
        assert plan_email.steps[0].required_tool == "google_gmail_search"

        req_cal = ChatRequest(message="What's on my calendar today?", session_id=sid, project_id=None)
        plan_cal = await planner.plan(req_cal)
        assert plan_cal.steps[0].required_tool == "google_calendar_list_events"

        req_drive = ChatRequest(message="Find my Kora documentation in Drive.", session_id=sid, project_id=None)
        plan_drive = await planner.plan(req_drive)
        assert plan_drive.steps[0].required_tool == "google_drive_search"

        req_task = ChatRequest(message="Add 'finish Kora Google integration' to my tasks.", session_id=sid, project_id=None)
        plan_task = await planner.plan(req_task)
        assert plan_task.steps[0].required_tool == "google_tasks_create"

        req_doc = ChatRequest(message="Create a document called Kora Roadmap.", session_id=sid, project_id=None)
        plan_doc = await planner.plan(req_doc)
        assert plan_doc.steps[0].required_tool == "google_docs_create"

        req_sheet = ChatRequest(message="Read rows A1:D20.", session_id=sid, project_id=None)
        plan_sheet = await planner.plan(req_sheet)
        assert plan_sheet.steps[0].required_tool == "google_sheets_read"
