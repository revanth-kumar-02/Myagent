"""
integrations.google — Unified Google Workspace Backend Services (V8)

Exposes authenticated client, token manager, structured errors, and services
for Gmail, Google Calendar, Google Drive, Google Tasks, Google Docs, and Google Sheets.
"""

from integrations.google.auth import GoogleAuthManager, get_google_auth_manager
from integrations.google.calendar import CalendarService
from integrations.google.client import GoogleWorkspaceClient
from integrations.google.docs import DocsService
from integrations.google.drive import DriveService
from integrations.google.errors import (
    GOOGLE_ERROR_CODES,
    GoogleAuthRequiredError,
    GoogleInvalidArgumentError,
    GoogleNotFoundError,
    GooglePermissionDeniedError,
    GoogleRateLimitedError,
    GoogleTokenExpiredError,
    GoogleWorkspaceError,
)
from integrations.google.gmail import GmailService
from integrations.google.sheets import SheetsService
from integrations.google.tasks import TasksService

__all__ = [
    "GoogleAuthManager",
    "get_google_auth_manager",
    "GoogleWorkspaceClient",
    "GmailService",
    "CalendarService",
    "DriveService",
    "TasksService",
    "DocsService",
    "SheetsService",
    "GoogleWorkspaceError",
    "GoogleAuthRequiredError",
    "GoogleTokenExpiredError",
    "GooglePermissionDeniedError",
    "GoogleNotFoundError",
    "GoogleRateLimitedError",
    "GoogleInvalidArgumentError",
    "GOOGLE_ERROR_CODES",
]
