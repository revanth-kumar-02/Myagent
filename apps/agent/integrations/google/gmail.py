"""
integrations.google.gmail — Gmail Service Integration

Provides real Gmail API v1 operations:
- search_emails(query, max_results)
- read_email(message_id)
- list_recent_emails(max_results, label_ids)
- create_draft(to, subject, body, thread_id)
- send_email(to, subject, body, thread_id)
- modify_labels(message_id, add_labels, remove_labels)
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any

from integrations.google.client import GoogleWorkspaceClient

GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailService:
    """Wrapper for Gmail REST API v1 endpoints."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def search_emails(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search messages matching query string."""
        url = f"{GMAIL_BASE_URL}/messages"
        params = {"q": query, "maxResults": min(max_results, 50)}
        data = await self.client.request("GET", url, params=params)

        messages = data.get("messages", [])
        results: list[dict[str, Any]] = []
        for m in messages:
            msg_id = m.get("id")
            if msg_id:
                details = await self.read_email(msg_id, format="metadata")
                results.append(details)
        return results

    async def list_recent_emails(self, max_results: int = 10, label_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """List recent messages optionally filtered by labels (e.g. INBOX, UNREAD)."""
        url = f"{GMAIL_BASE_URL}/messages"
        params: dict[str, Any] = {"maxResults": min(max_results, 50)}
        if label_ids:
            params["labelIds"] = label_ids
        data = await self.client.request("GET", url, params=params)

        messages = data.get("messages", [])
        results: list[dict[str, Any]] = []
        for m in messages:
            msg_id = m.get("id")
            if msg_id:
                details = await self.read_email(msg_id, format="metadata")
                results.append(details)
        return results

    async def read_email(self, message_id: str, format: str = "full") -> dict[str, Any]:
        """Fetch email metadata and decoded body content."""
        url = f"{GMAIL_BASE_URL}/messages/{message_id}"
        data = await self.client.request("GET", url, params={"format": format})

        headers_list = data.get("payload", {}).get("headers", [])
        headers_dict = {h.get("name", "").lower(): h.get("value", "") for h in headers_list}

        body_text = self._extract_body(data.get("payload", {}))
        return {
            "id": data.get("id", message_id),
            "thread_id": data.get("threadId", ""),
            "snippet": data.get("snippet", ""),
            "subject": headers_dict.get("subject", ""),
            "from": headers_dict.get("from", ""),
            "to": headers_dict.get("to", ""),
            "date": headers_dict.get("date", ""),
            "label_ids": data.get("labelIds", []),
            "body": body_text or data.get("snippet", ""),
        }

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a draft email without sending."""
        url = f"{GMAIL_BASE_URL}/drafts"
        raw_msg = self._build_raw_message(to, subject, body, thread_id)
        payload = {"message": {"raw": raw_msg}}
        if thread_id:
            payload["message"]["threadId"] = thread_id

        data = await self.client.request("POST", url, json_data=payload)
        return {
            "draft_id": data.get("id"),
            "message_id": data.get("message", {}).get("id"),
            "to": to,
            "subject": subject,
            "status": "draft_created",
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an email immediately."""
        url = f"{GMAIL_BASE_URL}/messages/send"
        raw_msg = self._build_raw_message(to, subject, body, thread_id)
        payload = {"raw": raw_msg}
        if thread_id:
            payload["threadId"] = thread_id

        data = await self.client.request("POST", url, json_data=payload)
        return {
            "id": data.get("id"),
            "thread_id": data.get("threadId"),
            "to": to,
            "subject": subject,
            "status": "sent",
        }

    async def modify_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add or remove labels from a message (e.g. mark read by removing UNREAD)."""
        url = f"{GMAIL_BASE_URL}/messages/{message_id}/modify"
        payload: dict[str, Any] = {
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        }
        data = await self.client.request("POST", url, json_data=payload)
        return {
            "id": data.get("id", message_id),
            "label_ids": data.get("labelIds", []),
            "status": "updated",
        }

    def _build_raw_message(self, to: str, subject: str, body: str, thread_id: str | None = None) -> str:
        """Construct RFC 2822 email and return URL-safe base64 encoded string."""
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return raw

    def _extract_body(self, payload: dict[str, Any]) -> str:
        """Extract plain text body recursively from payload parts."""
        if not payload:
            return ""

        body_data = payload.get("body", {}).get("data")
        mime_type = payload.get("mimeType", "")

        if mime_type.startswith("text/plain") and body_data:
            try:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            except Exception:
                pass

        parts = payload.get("parts", [])
        for part in parts:
            extracted = self._extract_body(part)
            if extracted:
                return extracted

        if body_data:
            try:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            except Exception:
                pass
        return ""
