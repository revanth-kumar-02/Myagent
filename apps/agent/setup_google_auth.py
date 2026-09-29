#!/usr/bin/env python3
"""
setup_google_auth.py — CLI Helper to Authorize Google Workspace for Kora

Walks through setting up Google OAuth credentials and authorizes:
- Gmail (read, compose, send)
- Calendar (view, create, update, delete)
- Drive (search, read, upload, manage)
- Tasks (list, create, update)
- Docs (read, edit)
- Sheets (read, write)

Tokens are securely saved to ~/.kora/google_tokens.json (mode 0600).
"""

import asyncio
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

# Ensure apps/agent is on sys.path
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from config import settings
from integrations.google.auth import GOOGLE_WORKSPACE_SCOPES, get_google_auth_manager


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self) -> None:
        query = urlparse(self.path).query
        params = parse_qs(query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                b"<h2 style='color:#10b981;'>Google Workspace Authorized Successfully!</h2>"
                b"<p>You can return to the Kora terminal now.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h3>Authorization failed or denied.</h3></body></html>")

    def log_message(self, format: str, *args: object) -> None:
        pass  # Quiet HTTP server logs


def _build_authorization_url(client_id: str, redirect_uri: str) -> str:
    """Build the OAuth2 consent URL for Google Workspace scopes."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_WORKSPACE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def _exchange_code_for_tokens(
    client_id: str, client_secret: str, code: str, redirect_uri: str
) -> dict[str, Any]:
    """Exchange OAuth authorization code for access and refresh tokens."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Failed to exchange code (HTTP {resp.status_code}): {resp.text}")

    data = resp.json()
    return cast(dict[str, Any], data if isinstance(data, dict) else {})


async def main() -> None:
    print("=" * 60)
    print(" Kora — Google Workspace Setup & Authorization")
    print("=" * 60)

    auth_manager = get_google_auth_manager()

    client_id = settings.google_client_id
    client_secret = settings.google_client_secret

    if not client_id or not client_secret:
        print("\n[!] Missing Google OAuth credentials in settings / environment.")
        print("Please configure them in apps/agent/.env or enter them now:")
        client_id_input = input("Enter GOOGLE_CLIENT_ID: ").strip()
        client_secret_input = input("Enter GOOGLE_CLIENT_SECRET: ").strip()
        if not client_id_input or not client_secret_input:
            print("Client ID and Client Secret are required. Exiting.")
            sys.exit(1)
        settings.google_client_id = client_id_input
        settings.google_client_secret = client_secret_input
        client_id = client_id_input
        client_secret = client_secret_input

    # Find an open port for the local callback receiver (trying 8765, 8766, 8767...)
    server: HTTPServer | None = None
    callback_port = 8765
    for p in range(8765, 8775):
        try:
            server = HTTPServer(("localhost", p), _CallbackHandler)
            callback_port = p
            break
        except OSError:
            continue

    redirect_uri = f"http://localhost:{callback_port}/api/auth/google/callback"
    auth_url = _build_authorization_url(client_id, redirect_uri=redirect_uri)
    print(f"\n1. Open the following URL in your browser to authorize Kora:\n\n{auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    auth_code = ""
    if server:
        print(f"2. Waiting for browser redirect callback on http://localhost:{callback_port}...")
        try:
            server.timeout = 180
            while not _CallbackHandler.auth_code:
                server.handle_request()
            auth_code = _CallbackHandler.auth_code or ""
            server.server_close()
        except Exception as e:
            print(f"Note: Local server listener ended ({e}).")

    if not auth_code:
        auth_code = input("2. Paste the authorization 'code' parameter from the redirect URL: ").strip()

    if not auth_code:
        print("No authorization code provided. Exiting.")
        sys.exit(1)

    print("\n3. Exchanging authorization code for tokens...")
    try:
        tokens = await _exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=auth_code,
            redirect_uri=redirect_uri,
        )
        access_token = str(tokens.get("access_token", ""))
        refresh_token = str(tokens.get("refresh_token", "")) if tokens.get("refresh_token") else None
        expires_in = int(tokens.get("expires_in", 3600))
        token_type = str(tokens.get("token_type", "Bearer"))

        auth_manager.set_credentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            scopes=str(tokens.get("scope", "")).split(),
        )
        print(f"[✓] Success! OAuth tokens saved to: {auth_manager._token_file}")
        print(f"    Granted scopes: {len(tokens.get('scope', '').split())} scopes")
        print("\nKora Google Workspace tools are now fully connected and ready to use!")
    except Exception as e:
        print(f"[✗] Token exchange failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
