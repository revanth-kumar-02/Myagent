"""
integrations.google.client — Unified Authenticated Google Workspace HTTP Client (V8)

Provides a centralized, resilient async client for all Google Workspace APIs:
Gmail, Google Calendar, Google Drive, Google Tasks, Google Docs, and Google Sheets.
Handles token attachment, automatic 401 refresh, structured error translation,
and rate-limit awareness without leaking credentials.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from integrations.google.auth import GoogleAuthManager, get_google_auth_manager
from integrations.google.errors import (
    GoogleAuthRequiredError,
    GoogleInvalidArgumentError,
    GoogleNotFoundError,
    GooglePermissionDeniedError,
    GoogleRateLimitedError,
    GoogleTokenExpiredError,
    GoogleWorkspaceError,
)

logger = structlog.get_logger(__name__)


class GoogleWorkspaceClient:
    """
    Central authenticated HTTP client interfacing with Google Workspace REST endpoints.
    """

    def __init__(self, auth_manager: GoogleAuthManager | None = None) -> None:
        self.auth = auth_manager or get_google_auth_manager()

    async def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
        retry_on_401: bool = True,
        timeout: float = 30.0,
    ) -> Any:
        """
        Execute an authenticated HTTP request against Google APIs.
        Automatically attaches bearer token and handles token refresh on 401.
        """
        token = await self.auth.get_valid_access_token()
        req_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as http_client:
                resp = await http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                )

            # Auto-refresh and retry once on 401 Unauthorized
            if resp.status_code == 401 and retry_on_401:
                logger.info("google_api_401_received_refreshing_token", url=url)
                new_token = await self.auth.refresh_token()
                req_headers["Authorization"] = f"Bearer {new_token}"
                async with httpx.AsyncClient(timeout=timeout) as http_client:
                    resp = await http_client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=req_headers,
                    )

            return self._handle_response(resp)

        except (GoogleWorkspaceError, GoogleAuthRequiredError):
            raise
        except httpx.TimeoutException as te:
            raise GoogleWorkspaceError(f"Google Workspace API request timed out: {te}") from te
        except Exception as e:
            logger.error("google_api_unhandled_error", url=url, error=str(e))
            raise GoogleWorkspaceError(f"Google Workspace request failed: {e}") from e

    def _handle_response(self, resp: httpx.Response) -> Any:
        """Translates HTTP responses and status codes into structured exceptions."""
        if 200 <= resp.status_code < 300:
            if resp.status_code == 204 or not resp.content:
                empty: dict[str, Any] = {}
                return empty
            try:
                return resp.json()
            except Exception:
                return resp.text

        status = resp.status_code
        err_msg = "Google Workspace API error"
        details: dict[str, Any] = {"status_code": status}

        try:
            body = resp.json()
            if isinstance(body, dict) and "error" in body:
                error_obj = body["error"]
                if isinstance(error_obj, dict):
                    err_msg = error_obj.get("message", err_msg)
                    details["google_error"] = error_obj
                elif isinstance(error_obj, str):
                    err_msg = error_obj
        except Exception:
            err_msg = f"HTTP {status}: {resp.text[:200]}"

        if status == 401:
            raise GoogleTokenExpiredError(f"Google authorization expired: {err_msg}", details)
        elif status == 403:
            raise GooglePermissionDeniedError(f"Permission denied: {err_msg}", details)
        elif status == 404:
            raise GoogleNotFoundError(f"Resource not found: {err_msg}", details)
        elif status == 429:
            raise GoogleRateLimitedError(f"Google API rate limit exceeded: {err_msg}", details)
        elif status == 400:
            raise GoogleInvalidArgumentError(f"Invalid argument: {err_msg}", details)
        else:
            raise GoogleWorkspaceError(f"Google API error ({status}): {err_msg}", details)
