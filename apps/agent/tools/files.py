"""
tools.files — File and Directory Management Tools (V8)

Tools:
  - FileReadTool: Read file text content
  - FileWriteTool: Write/overwrite file text content
  - FileCreateTool: Create new empty file
  - FileMoveTool: Move file from source to destination
  - FileRenameTool: Rename file
  - FileDeleteTool: Delete file
  - DirectoryOpsTool: List, create, or remove directories
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import aiofiles

from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult


class FileReadTool(BaseTool):
    """Read textual content from a local file."""

    @property
    def tool_id(self) -> str:
        return "file_read"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Read textual content from a specified file path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
                "max_lines": {"type": "integer", "description": "Optional maximum lines to read"},
            },
            "required": ["path"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_str = p.get("path", "")
        if not path_str:
            return self._make_result(error="Missing required parameter: 'path'")
        path = Path(path_str)
        if not path.exists():
            return self._make_result(error=f"File not found: {path}")
        if not path.is_file():
            return self._make_result(error=f"Path is not a file: {path}")

        max_lines = p.get("max_lines")
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
                if max_lines:
                    lines = [await f.readline() for _ in range(max_lines)]
                    content = "".join(lines)
                else:
                    content = await f.read()

            return self._make_result(output={"path": str(path), "content": content, "size_bytes": len(content.encode("utf-8"))})
        except Exception as e:
            return self._make_result(error=f"Failed to read file: {e}")


class FileWriteTool(BaseTool):
    """Write or overwrite textual content to a local file."""

    @property
    def tool_id(self) -> str:
        return "file_write"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Write textual content to a specified file path (creates parent directories if missing)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write to"},
                "content": {"type": "string", "description": "Textual content to write"},
                "append": {"type": "boolean", "description": "Whether to append rather than overwrite"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_str = p.get("path", "")
        content = p.get("content", "")
        if not path_str:
            return self._make_result(error="Missing required parameter: 'path'")
        path = Path(path_str)
        append = p.get("append", False)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            async with aiofiles.open(path, mode=mode, encoding="utf-8") as f:
                await f.write(content)

            return self._make_result(output={"path": str(path), "bytes_written": len(content.encode("utf-8")), "mode": mode})
        except Exception as e:
            return self._make_result(error=f"Failed to write file: {e}")


class FileCreateTool(BaseTool):
    """Create a new empty file."""

    @property
    def tool_id(self) -> str:
        return "file_create"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Create a new file at the specified path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to create"},
            },
            "required": ["path"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_str = p.get("path", "")
        if not path_str:
            return self._make_result(error="Missing required parameter: 'path'")
        path = Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            return self._make_result(output={"path": str(path), "created": True})
        except Exception as e:
            return self._make_result(error=f"Failed to create file: {e}")


class FileMoveTool(BaseTool):
    """Move a file from source path to destination path."""

    @property
    def tool_id(self) -> str:
        return "file_move"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Move a file from source path to destination path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path"},
                "destination": {"type": "string", "description": "Destination file path"},
            },
            "required": ["source", "destination"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        src_str = p.get("source", "")
        dst_str = p.get("destination", "")
        if not src_str or not dst_str:
            return self._make_result(error="Missing required parameters: 'source' and 'destination'")
        src = Path(src_str)
        dst = Path(dst_str)
        if not src.exists():
            return self._make_result(error=f"Source path does not exist: {src}")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return self._make_result(output={"source": str(src), "destination": str(dst), "moved": True})
        except Exception as e:
            return self._make_result(error=f"Failed to move file: {e}")


class FileRenameTool(BaseTool):
    """Rename a file or directory."""

    @property
    def tool_id(self) -> str:
        return "file_rename"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Rename a file or directory."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file to rename"},
                "new_name": {"type": "string", "description": "New filename"},
            },
            "required": ["path", "new_name"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_str = p.get("path", "")
        new_name = p.get("new_name", "")
        if not path_str or not new_name:
            return self._make_result(error="Missing required parameters: 'path' and 'new_name'")
        path = Path(path_str)
        if not path.exists():
            return self._make_result(error=f"Path not found: {path}")

        try:
            new_path = path.parent / new_name
            path.rename(new_path)
            return self._make_result(output={"old_path": str(path), "new_path": str(new_path), "renamed": True})
        except Exception as e:
            return self._make_result(error=f"Failed to rename: {e}")


class FileDeleteTool(BaseTool):
    """Delete a file permanently."""

    @property
    def tool_id(self) -> str:
        return "file_delete"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "Delete a file permanently from disk."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path of file to delete"},
            },
            "required": ["path"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_str = p.get("path", "")
        if not path_str:
            return self._make_result(error="Missing required parameter: 'path'")
        path = Path(path_str)
        if not path.exists():
            return self._make_result(error=f"File not found: {path}")

        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            return self._make_result(output={"path": str(path), "deleted": True})
        except Exception as e:
            return self._make_result(error=f"Failed to delete path: {e}")


class DirectoryOpsTool(BaseTool):
    """List, create, or remove directories."""

    @property
    def tool_id(self) -> str:
        return "directory_ops"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILES

    @property
    def description(self) -> str:
        return "List contents, create, or remove a directory."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create", "remove"], "description": "Directory action"},
                "path": {"type": "string", "description": "Directory path"},
            },
            "required": ["action", "path"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "list")
        path_str = p.get("path", "")
        if not path_str:
            return self._make_result(error="Missing required parameter: 'path'")
        path = Path(path_str)

        try:
            if action == "list":
                if not path.exists() or not path.is_dir():
                    return self._make_result(error=f"Directory does not exist: {path}")
                items = [{"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0} for item in path.iterdir()]
                return self._make_result(output={"path": str(path), "items": items, "count": len(items)})

            elif action == "create":
                path.mkdir(parents=True, exist_ok=True)
                return self._make_result(output={"path": str(path), "created": True})

            elif action == "remove":
                if path.exists() and path.is_dir():
                    shutil.rmtree(path)
                return self._make_result(output={"path": str(path), "removed": True})

            return self._make_result(error=f"Unknown directory action: {action}")
        except Exception as e:
            return self._make_result(error=f"Directory operation failed: {e}")
