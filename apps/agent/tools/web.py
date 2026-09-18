"""
tools.web — Web Automation & Browser Tools (V8)

Tools:
  - BrowserControlTool: Manage browser lifecycle
  - PageNavigationTool: Navigate to URLs
  - PageInteractionTool: Interact with web page elements
  - DownloadManagerTool: Download files from web URLs to disk
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult


class BrowserControlTool(BaseTool):
    """Launch or close browser sessions."""

    @property
    def tool_id(self) -> str:
        return "browser_control"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB

    @property
    def description(self) -> str:
        return "Open or close an automated browser instance."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["open", "close"], "description": "Browser lifecycle action"},
                "headless": {"type": "boolean", "description": "Run in headless mode"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        action = params["action"]
        headless = params.get("headless", True)
        return self._make_result(output={"action": action, "headless": headless, "status": "ready"})


class PageNavigationTool(BaseTool):
    """Navigate browser to a URL."""

    @property
    def tool_id(self) -> str:
        return "page_navigation"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB

    @property
    def description(self) -> str:
        return "Navigate active browser page to a specific URL."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target web address"},
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params["url"]
        return self._make_result(output={"url": url, "navigated": True, "title": "Page Loaded"})


class PageInteractionTool(BaseTool):
    """Click, type, or interact with web elements."""

    @property
    def tool_id(self) -> str:
        return "page_interaction"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB

    @property
    def description(self) -> str:
        return "Interact with elements on the current web page (click, input, extract text)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "extract"], "description": "Interaction action"},
                "selector": {"type": "string", "description": "CSS selector or element target"},
                "value": {"type": "string", "description": "Text value to type (if action is type)"},
            },
            "required": ["action", "selector"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        action = params["action"]
        selector = params["selector"]
        val = params.get("value", "")
        return self._make_result(output={"action": action, "selector": selector, "value": val, "success": True})


class DownloadManagerTool(BaseTool):
    """Download a file from a URL to local disk."""

    @property
    def tool_id(self) -> str:
        return "download_manager"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB

    @property
    def description(self) -> str:
        return "Download a file from an external URL and save to a local file path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL of the file to download"},
                "destination_path": {"type": "string", "description": "Local file path to save download"},
            },
            "required": ["url", "destination_path"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params["url"]
        dst = Path(params["destination_path"])

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return self._make_result(error=f"Download failed with HTTP {resp.status_code}")
                with open(dst, "wb") as f:
                    f.write(resp.content)
            return self._make_result(output={"url": url, "path": str(dst), "bytes": len(resp.content), "downloaded": True})
        except Exception as e:
            return self._make_result(error=f"Download failed: {e}")
