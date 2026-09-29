"""
integrations.google.docs — Google Docs Service Integration (V8)

Provides direct async integration with Google Docs API v1:
- Read document structure and plain text content
- Create blank document
- Append text/paragraphs
- Insert text at specific index or location
- Execute batchUpdate requests
Note: File discovery and metadata are handled via DriveService.
"""

from __future__ import annotations

from typing import Any, cast

import structlog

from integrations.google.client import GoogleWorkspaceClient
from integrations.google.errors import GoogleInvalidArgumentError

logger = structlog.get_logger(__name__)

DOCS_BASE_URL = "https://docs.googleapis.com/v1/documents"


class DocsService:
    """Service wrapper for Google Docs API v1."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def get_document(self, document_id: str) -> dict[str, Any]:
        """Fetch raw document structure from Google Docs API."""
        if not document_id:
            raise GoogleInvalidArgumentError("document_id is required.")
        url = f"{DOCS_BASE_URL}/{document_id}"
        res = await self.client.request("GET", url)
        return cast(dict[str, Any], res if isinstance(res, dict) else {})

    async def read_document_text(self, document_id: str) -> dict[str, Any]:
        """
        Extract clean, readable text from a Google Document.
        Parses body content elements, paragraphs, and tables.
        """
        doc = await self.get_document(document_id)
        title = doc.get("title", "Untitled Document")
        body = doc.get("body", {})
        content_elements = body.get("content", [])

        extracted_text_chunks: list[str] = []
        for element in content_elements:
            if "paragraph" in element:
                para = element["paragraph"]
                for p_elem in para.get("elements", []):
                    text_run = p_elem.get("textRun")
                    if text_run and "content" in text_run:
                        extracted_text_chunks.append(text_run["content"])
            elif "table" in element:
                table = element["table"]
                for row in table.get("tableRows", []):
                    row_cells = []
                    for cell in row.get("tableCells", []):
                        cell_text = "".join(
                            tr.get("textRun", {}).get("content", "").strip()
                            for elem in cell.get("content", [])
                            for tr in elem.get("paragraph", {}).get("elements", [])
                        )
                        row_cells.append(cell_text)
                    extracted_text_chunks.append(" | ".join(row_cells) + "\n")

        full_text = "".join(extracted_text_chunks)
        # Determine end index for subsequent appends
        end_index = content_elements[-1].get("endIndex", 1) if content_elements else 1

        return {
            "document_id": document_id,
            "title": title,
            "revision_id": doc.get("revisionId"),
            "content": full_text,
            "end_index": end_index,
        }

    async def create_document(self, title: str) -> dict[str, Any]:
        """Create a new Google Document."""
        if not title or not title.strip():
            raise GoogleInvalidArgumentError("Document title is required.")

        body = {"title": title.strip()}
        url = DOCS_BASE_URL
        data = await self.client.request("POST", url, json_data=body)
        logger.info("google_doc_created", document_id=data.get("documentId"), title=title)
        return {
            "document_id": data.get("documentId"),
            "title": data.get("title"),
            "revision_id": data.get("revisionId"),
        }

    async def append_text(self, document_id: str, text: str) -> dict[str, Any]:
        """
        Append text to the end of a document.
        First inspects the document end index, then sends an insertText batch update.
        """
        if not document_id:
            raise GoogleInvalidArgumentError("document_id is required.")
        if not text:
            raise GoogleInvalidArgumentError("Text to append is required.")

        # Read document to find end index
        doc_info = await self.read_document_text(document_id)
        # Google Docs endIndex is 1-indexed, and last character is a newline (end of body)
        # To insert at end, index is doc_info['end_index'] - 1
        insert_index = max(1, doc_info.get("end_index", 1) - 1)

        requests = [
            {
                "insertText": {
                    "location": {"index": insert_index},
                    "text": text if text.endswith("\n") else f"\n{text}\n",
                }
            }
        ]
        return await self.batch_update(document_id, requests)

    async def insert_text(
        self, document_id: str, text: str, index: int = 1
    ) -> dict[str, Any]:
        """Insert text at a specific index in the document."""
        if not document_id:
            raise GoogleInvalidArgumentError("document_id is required.")
        if not text:
            raise GoogleInvalidArgumentError("Text is required.")
        if index < 1:
            raise GoogleInvalidArgumentError("Index must be >= 1.")

        requests = [
            {
                "insertText": {
                    "location": {"index": index},
                    "text": text,
                }
            }
        ]
        return await self.batch_update(document_id, requests)

    async def batch_update(
        self, document_id: str, requests: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Execute a list of batch update requests on a document."""
        if not document_id:
            raise GoogleInvalidArgumentError("document_id is required.")
        if not requests:
            return {"document_id": document_id, "replies": []}

        url = f"{DOCS_BASE_URL}/{document_id}:batchUpdate"
        data = await self.client.request("POST", url, json_data={"requests": requests})
        logger.info("google_doc_batch_updated", document_id=document_id, num_requests=len(requests))
        return {
            "document_id": data.get("documentId", document_id),
            "replies": data.get("replies", []),
        }
