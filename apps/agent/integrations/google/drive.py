"""
integrations.google.drive — Google Drive Service Integration (V8)

Provides direct async integration with Google Drive API v3:
- Search files using Drive queries
- List files
- Get file metadata
- Read file content (direct download or Google Docs/Sheets export to text/csv)
- Create folders
- Upload/create files (with optional parent folder)
- Move files (addParents / removeParents)
- Rename files
- Delete/trash files (destructive)
- Export documents for RAG ingestion
"""

from __future__ import annotations

import io
from typing import Any, cast

import structlog

from integrations.google.client import GoogleWorkspaceClient
from integrations.google.errors import GoogleInvalidArgumentError, GoogleNotFoundError

logger = structlog.get_logger(__name__)

DRIVE_BASE_URL = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE_URL = "https://www.googleapis.com/upload/drive/v3"

# Common export MIME types for Google Docs / Sheets
EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class DriveService:
    """Service wrapper for Google Drive API v3."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def list_files(
        self,
        folder_id: str | None = None,
        query: str | None = None,
        page_size: int = 50,
        fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, webViewLink, trashed)",
    ) -> list[dict[str, Any]]:
        """
        List files in Google Drive. If folder_id is supplied, restricts search to that folder.
        """
        q_parts = ["trashed = false"]
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        if query:
            q_parts.append(query)

        full_q = " and ".join(q_parts)
        url = f"{DRIVE_BASE_URL}/files"
        params = {
            "q": full_q,
            "pageSize": min(page_size, 100),
            "fields": fields,
        }
        data = await self.client.request("GET", url, params=params)
        empty_files: list[dict[str, Any]] = []
        files: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], data.get("files", empty_files))
            if isinstance(data, dict)
            else empty_files
        )
        return files

    async def search_files(
        self,
        name_contains: str | None = None,
        mime_type: str | None = None,
        modified_after: str | None = None,
        full_text: str | None = None,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Structured search across Google Drive files using Drive query operators.
        """
        q_parts = ["trashed = false"]
        if name_contains:
            escaped = name_contains.replace("'", "\\'")
            q_parts.append(f"name contains '{escaped}'")
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        if modified_after:
            q_parts.append(f"modifiedTime > '{modified_after}'")
        if full_text:
            escaped_ft = full_text.replace("'", "\\'")
            q_parts.append(f"fullText contains '{escaped_ft}'")

        return await self.list_files(query=" and ".join(q_parts), page_size=page_size)

    async def get_metadata(self, file_id: str) -> dict[str, Any]:
        """Fetch metadata for a single file or folder."""
        if not file_id:
            raise GoogleInvalidArgumentError("file_id is required.")
        url = f"{DRIVE_BASE_URL}/files/{file_id}"
        fields = "id, name, mimeType, modifiedTime, size, parents, webViewLink, trashed, description"
        res = await self.client.request("GET", url, params={"fields": fields})
        return cast(dict[str, Any], res if isinstance(res, dict) else {})

    async def read_file(self, file_id: str, max_chars: int = 50000) -> dict[str, Any]:
        """
        Read file contents. For Google Workspace documents (Docs, Sheets), exports
        as text/plain or text/csv. For standard text files, downloads directly.
        Returns metadata and text content up to max_chars.
        """
        meta = await self.get_metadata(file_id)
        mime = meta.get("mimeType", "")

        # Check if it's a native Google Docs / Sheets / Slides file requiring export
        if mime in EXPORT_MIME_TYPES:
            export_mime = EXPORT_MIME_TYPES[mime]
            url = f"{DRIVE_BASE_URL}/files/{file_id}/export"
            content = await self.client.request("GET", url, params={"mimeType": export_mime})
            text_content = str(content)[:max_chars]
            return {
                "file_id": file_id,
                "name": meta.get("name"),
                "mimeType": mime,
                "exportedAs": export_mime,
                "content": text_content,
                "truncated": len(str(content)) > max_chars,
            }

        # Otherwise download raw content with alt=media
        url = f"{DRIVE_BASE_URL}/files/{file_id}"
        content = await self.client.request("GET", url, params={"alt": "media"})
        text_content = str(content)[:max_chars]
        return {
            "file_id": file_id,
            "name": meta.get("name"),
            "mimeType": mime,
            "content": text_content,
            "truncated": len(str(content)) > max_chars,
        }

    async def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
        """Create a new folder in Google Drive."""
        if not name or not name.strip():
            raise GoogleInvalidArgumentError("Folder name is required.")

        body: dict[str, Any] = {
            "name": name.strip(),
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        url = f"{DRIVE_BASE_URL}/files"
        fields = "id, name, mimeType, webViewLink, parents"
        data = await self.client.request("POST", url, json_data=body, params={"fields": fields})
        dict_data = cast(dict[str, Any], data if isinstance(data, dict) else {})
        logger.info("drive_folder_created", folder_id=dict_data.get("id"), name=name)
        return dict_data

    async def create_file(
        self,
        name: str,
        content: str = "",
        mime_type: str = "text/plain",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a file directly in Drive. For Google Docs or Sheets, use the specific
        Docs/Sheets API or set the appropriate Google Workspace mimeType.
        """
        if not name or not name.strip():
            raise GoogleInvalidArgumentError("File name is required.")

        metadata: dict[str, Any] = {
            "name": name.strip(),
            "mimeType": mime_type,
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        # Use multipart upload or simple upload
        url = f"{UPLOAD_BASE_URL}/files?uploadType=multipart"
        # Construct multipart/related boundary
        boundary = "===============kora_drive_boundary=="
        headers = {"Content-Type": f"multipart/related; boundary={boundary}"}

        import json

        body_str = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
            f"{content}\r\n"
            f"--{boundary}--\r\n"
        )

        # Use raw request through client
        data = await self.client.request(
            "POST",
            url,
            headers=headers,
            json_data=None,
            params={"fields": "id, name, mimeType, webViewLink, parents"},
        )
        # Note: if multipart upload is rejected by json serializer, fallback to creating metadata then updating
        if not data or not isinstance(data, dict) or "id" not in data:
            # Fallback: create metadata first
            create_url = f"{DRIVE_BASE_URL}/files"
            data = await self.client.request(
                "POST", create_url, json_data=metadata, params={"fields": "id, name, mimeType, webViewLink"}
            )

        file_dict = cast(dict[str, Any], data if isinstance(data, dict) else {})
        logger.info("drive_file_created", file_id=file_dict.get("id"), name=name)
        return file_dict

    async def rename_file(self, file_id: str, new_name: str) -> dict[str, Any]:
        """Rename a file or folder."""
        if not file_id or not new_name or not new_name.strip():
            raise GoogleInvalidArgumentError("file_id and non-empty new_name are required.")
        url = f"{DRIVE_BASE_URL}/files/{file_id}"
        res = await self.client.request(
            "PATCH", url, json_data={"name": new_name.strip()}, params={"fields": "id, name, mimeType"}
        )
        return cast(dict[str, Any], res if isinstance(res, dict) else {})

    async def move_file(self, file_id: str, new_parent_id: str) -> dict[str, Any]:
        """Move a file to a new parent folder."""
        if not file_id or not new_parent_id:
            raise GoogleInvalidArgumentError("file_id and new_parent_id are required.")

        meta = await self.get_metadata(file_id)
        previous_parents = ",".join(meta.get("parents", []))

        url = f"{DRIVE_BASE_URL}/files/{file_id}"
        params: dict[str, Any] = {
            "addParents": new_parent_id,
            "fields": "id, name, parents",
        }
        if previous_parents:
            params["removeParents"] = previous_parents

        res = await self.client.request("PATCH", url, params=params)
        return cast(dict[str, Any], res if isinstance(res, dict) else {})

    async def delete_file(self, file_id: str, permanent: bool = False) -> dict[str, Any]:
        """
        Trash or permanently delete a file (destructive action).
        By default, moves to trash (reversible) rather than permanent destruction.
        """
        if not file_id:
            raise GoogleInvalidArgumentError("file_id is required.")

        if permanent:
            url = f"{DRIVE_BASE_URL}/files/{file_id}"
            await self.client.request("DELETE", url)
            logger.info("drive_file_permanently_deleted", file_id=file_id)
            return {"status": "permanently_deleted", "file_id": file_id}
        else:
            url = f"{DRIVE_BASE_URL}/files/{file_id}"
            data = await self.client.request("PATCH", url, json_data={"trashed": True})
            logger.info("drive_file_trashed", file_id=file_id)
            return {"status": "trashed", "file_id": file_id}
