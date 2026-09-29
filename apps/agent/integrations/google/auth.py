"""
integrations.google.auth — Google Workspace OAuth2 Token & Credential Manager

Manages secure storage, lifecycle, verification, and automatic refresh of Google OAuth tokens.
Tokens are persisted in ~/.kora/google_tokens.json with strict file permissions.
Never exposes raw tokens in logs or telemetry.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, cast

import httpx
import structlog

from config import settings
from integrations.google.errors import GoogleAuthRequiredError, GoogleTokenExpiredError

logger = structlog.get_logger(__name__)

# Scopes adhering to least-privilege principles
GOOGLE_WORKSPACE_SCOPES = [
    # Gmail: read and draft/send
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    # Calendar: full calendar event management
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    # Drive: manage drive files opened/created by app & search
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    # Tasks: task management
    "https://www.googleapis.com/auth/tasks",
    # Docs: document editing
    "https://www.googleapis.com/auth/documents",
    # Sheets: spreadsheet editing
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleAuthManager:
    """
    Manages OAuth2 token lifecycle for Google Workspace APIs.
    """

    def __init__(self, token_file: Path | str | None = None) -> None:
        self._token_file = Path(token_file) if token_file else settings.google_token_file
        self._tokens: dict[str, Any] = {}
        self._load_tokens_from_disk()

    def _load_tokens_from_disk(self) -> None:
        """Load stored tokens from disk if present."""
        if not self._token_file.exists():
            return
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._tokens = data
            logger.info("google_tokens_loaded_from_disk", path=str(self._token_file))
        except Exception as e:
            logger.warning("failed_to_load_google_tokens", error=str(e))

    def _save_tokens_to_disk(self) -> None:
        """Persist tokens to disk with secure 0600 permissions."""
        try:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self._token_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._tokens, f, indent=2)
            os.chmod(temp_file, 0o600)
            temp_file.replace(self._token_file)
            os.chmod(self._token_file, 0o600)
            logger.debug("google_tokens_saved_to_disk")
        except Exception as e:
            logger.error("failed_to_save_google_tokens", error=str(e))

    def is_authenticated(self) -> bool:
        """Check whether we have an access or refresh token present."""
        return bool(self._tokens.get("access_token") or self._tokens.get("refresh_token"))

    def set_credentials(
        self,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int = 3600,
        token_type: str = "Bearer",
        scopes: list[str] | None = None,
    ) -> None:
        """Save received OAuth credentials."""
        now = time.time()
        self._tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token or self._tokens.get("refresh_token", ""),
            "token_type": token_type,
            "expires_at": now + expires_in - 60,  # 60s buffer
            "scopes": scopes or self._tokens.get("scopes", GOOGLE_WORKSPACE_SCOPES),
        }
        self._save_tokens_to_disk()

    async def get_valid_access_token(self) -> str:
        """
        Return a valid access token, automatically refreshing it if expired.
        Raises GoogleAuthRequiredError or GoogleTokenExpiredError if unauthenticated.
        """
        if not self.is_authenticated():
            raise GoogleAuthRequiredError(
                "Google authorization is required. Please authenticate your Google account to access Google Workspace tools."
            )

        now = time.time()
        expires_at = self._tokens.get("expires_at", 0)
        access_token = self._tokens.get("access_token")

        if isinstance(access_token, str) and now < expires_at:
            return access_token

        # Access token is missing or expired, attempt refresh
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise GoogleTokenExpiredError(
                "Google access token has expired and no refresh token is available. Please re-authorize Google Workspace."
            )

        return await self.refresh_token()

    async def refresh_token(self) -> str:
        """Refresh expired access token using Google OAuth token endpoint."""
        refresh_token = self._tokens.get("refresh_token")
        client_id = settings.google_client_id
        client_secret = settings.google_client_secret

        if not refresh_token:
            raise GoogleTokenExpiredError("No refresh token available to refresh Google session.")

        if not client_id or not client_secret:
            logger.warning("missing_google_oauth_client_credentials_during_refresh")
            raise GoogleAuthRequiredError(
                "Google OAuth client credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are not configured."
            )

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data=payload)

            if resp.status_code != 200:
                logger.error("google_token_refresh_failed", status=resp.status_code)
                raise GoogleTokenExpiredError(
                    f"Google token refresh failed (HTTP {resp.status_code}). Please re-authorize Google Workspace."
                )

            data = resp.json()
            new_access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not isinstance(new_access_token, str) or not new_access_token:
                raise GoogleTokenExpiredError("Invalid token response from Google OAuth refresh endpoint.")

            self.set_credentials(
                access_token=new_access_token,
                refresh_token=data.get("refresh_token") or refresh_token,
                expires_in=expires_in,
            )
            return new_access_token
        except (GoogleTokenExpiredError, GoogleAuthRequiredError):
            raise
        except Exception as e:
            logger.error("google_token_refresh_exception", error=str(e))
            raise GoogleTokenExpiredError(f"Error during Google token refresh: {e}") from e

    def get_authorization_url(self, redirect_uri: str | None = None, state: str = "") -> str:
        """Generate Google OAuth2 consent URL for all workspace scopes."""
        from urllib.parse import urlencode

        client_id = settings.google_client_id
        if not client_id:
            raise GoogleAuthRequiredError("GOOGLE_CLIENT_ID is not set in environment or settings.")

        redirect = redirect_uri or settings.google_redirect_uri
        params = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(GOOGLE_WORKSPACE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: str | None = None
    ) -> dict[str, Any]:
        """Exchange an OAuth authorization code for access and refresh tokens."""
        from integrations.google.errors import GoogleWorkspaceError

        client_id = settings.google_client_id
        client_secret = settings.google_client_secret
        if not client_id or not client_secret:
            raise GoogleAuthRequiredError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required to exchange authorization code."
            )

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or settings.google_redirect_uri,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data=payload)

        if resp.status_code != 200:
            raise GoogleWorkspaceError(
                f"Failed to exchange OAuth code for tokens (HTTP {resp.status_code}): {resp.text}"
            )

        data = resp.json()
        access_token = str(data.get("access_token", ""))
        refresh_token = str(data.get("refresh_token", "")) if data.get("refresh_token") else None
        expires_in = int(data.get("expires_in", 3600))
        token_type = str(data.get("token_type", "Bearer"))

        self.set_credentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            scopes=str(data.get("scope", "")).split(),
        )
        return cast(dict[str, Any], data if isinstance(data, dict) else {})

    def clear(self) -> None:
        """Clear cached tokens."""
        self._tokens = {}
        if self._token_file.exists():
            try:
                self._token_file.unlink()
            except Exception:
                pass


# Global Auth Manager instance
_default_auth_manager: GoogleAuthManager | None = None


def get_google_auth_manager() -> GoogleAuthManager:
    global _default_auth_manager
    if _default_auth_manager is None:
        _default_auth_manager = GoogleAuthManager()
    return _default_auth_manager
