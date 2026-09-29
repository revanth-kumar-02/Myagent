"""
tools.google — Google Workspace Agent Tools Package (V8)

Exports all Google Workspace tools for Kora:
- Gmail: search, read, draft, send, unified
- Calendar: list_events, create_event, update_event, delete_event, unified
- Drive: search, read, create_folder, upload, delete, unified
- Tasks: list, create, complete, unified
- Docs: read, create, update, unified
- Sheets: read, write, append, unified
"""

from tools.google.calendar_tools import (
    CalendarCreateEventTool,
    CalendarDeleteEventTool,
    CalendarListEventsTool,
    CalendarUpdateEventTool,
    GoogleCalendarTool,
)
from tools.google.docs_tools import (
    DocsCreateTool,
    DocsReadTool,
    DocsUpdateTool,
    GoogleDocsTool,
)
from tools.google.drive_tools import (
    DriveCreateFolderTool,
    DriveDeleteTool,
    DriveReadTool,
    DriveSearchTool,
    GoogleDriveTool,
)
from tools.google.gmail_tools import (
    GmailDraftTool,
    GmailReadTool,
    GmailSearchTool,
    GmailSendTool,
    GoogleGmailTool,
)
from tools.google.sheets_tools import (
    GoogleSheetsTool,
    SheetsAppendTool,
    SheetsReadTool,
    SheetsWriteTool,
)
from tools.google.tasks_tools import (
    GoogleTasksTool,
    TasksCompleteTool,
    TasksCreateTool,
    TasksListTool,
)

__all__ = [
    # Gmail
    "GmailSearchTool",
    "GmailReadTool",
    "GmailDraftTool",
    "GmailSendTool",
    "GoogleGmailTool",
    # Calendar
    "CalendarListEventsTool",
    "CalendarCreateEventTool",
    "CalendarUpdateEventTool",
    "CalendarDeleteEventTool",
    "GoogleCalendarTool",
    # Drive
    "DriveSearchTool",
    "DriveReadTool",
    "DriveCreateFolderTool",
    "DriveDeleteTool",
    "GoogleDriveTool",
    # Tasks
    "TasksListTool",
    "TasksCreateTool",
    "TasksCompleteTool",
    "GoogleTasksTool",
    # Docs
    "DocsReadTool",
    "DocsCreateTool",
    "DocsUpdateTool",
    "GoogleDocsTool",
    # Sheets
    "SheetsReadTool",
    "SheetsWriteTool",
    "SheetsAppendTool",
    "GoogleSheetsTool",
]
