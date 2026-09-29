"""
integrations.google.errors — Structured Google Workspace Exceptions (V8)

Provides normalized, structured error classes ensuring no sensitive credentials
or raw authorization tokens ever leak into logs, telemetry, or user/agent context.
"""

from __future__ import annotations

from typing import Any


class GoogleWorkspaceError(Exception):
    """Base exception for all Google Workspace integration errors."""

    error_code: str = "GOOGLE_API_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class GoogleAuthRequiredError(GoogleWorkspaceError):
    """Raised when Google authorization/tokens are missing or uninitialized."""

    error_code: str = "GOOGLE_AUTH_REQUIRED"


class GoogleTokenExpiredError(GoogleWorkspaceError):
    """Raised when Google access token is expired and refresh token failed."""

    error_code: str = "GOOGLE_TOKEN_EXPIRED"


class GooglePermissionDeniedError(GoogleWorkspaceError):
    """Raised when Google API returns HTTP 403 Forbidden or insufficient scope."""

    error_code: str = "GOOGLE_PERMISSION_DENIED"


class GoogleNotFoundError(GoogleWorkspaceError):
    """Raised when the requested resource (message, event, file, doc) was not found (HTTP 404)."""

    error_code: str = "GOOGLE_NOT_FOUND"


class GoogleRateLimitedError(GoogleWorkspaceError):
    """Raised when Google API quota or rate limit is reached (HTTP 429)."""

    error_code: str = "GOOGLE_RATE_LIMITED"


class GoogleInvalidArgumentError(GoogleWorkspaceError):
    """Raised when parameter validation fails or invalid arguments are supplied."""

    error_code: str = "GOOGLE_INVALID_ARGUMENT"


GOOGLE_ERROR_CODES = (
    "GOOGLE_AUTH_REQUIRED",
    "GOOGLE_TOKEN_EXPIRED",
    "GOOGLE_PERMISSION_DENIED",
    "GOOGLE_NOT_FOUND",
    "GOOGLE_RATE_LIMITED",
    "GOOGLE_INVALID_ARGUMENT",
    "GOOGLE_API_ERROR",
)
