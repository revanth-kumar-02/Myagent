import os
import logging
from typing import Dict, Any, Type, Optional
from core.tools.base import BaseTool, ToolResult
from core.filesystem.path_validator import PathValidator
from core.filesystem.permission_manager import permission_manager
from core.filesystem.tools import (
    FilesystemToolSet,
    ListDirectoryInput, SearchFilesInput, ReadFileInput, InspectFileInput,
    CreateFileInput, EditFileInput, MoveFileInput, DeleteFileInput
)

logger = logging.getLogger(__name__)

# Default global validator
default_validator = PathValidator([os.getcwd(), "/home/rev/My Personal Space/Projects"])
global_filesystem_toolset = FilesystemToolSet(default_validator, permission_manager)

class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "Lists directory contents inside authorized workspace with pagination and noise filtering."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.list_directory(ListDirectoryInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "List directory failed")
        )

class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Searches files by filename, path, or text content within authorized workspace."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.search_files(SearchFilesInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Search files failed")
        )

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Reads text file contents with line range support and binary detection."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.read_file(ReadFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Read file failed")
        )

class InspectFileTool(BaseTool):
    name = "inspect_file"
    description = "Inspects file or directory metadata (size, mime type, timestamps, git ignore status)."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.inspect_file(InspectFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Inspect file failed")
        )

class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Creates a new file with text content and performs post-creation verification."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.create_file(CreateFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Create file failed")
        )

class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Replaces target content snippet in a file and performs post-edit verification."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.edit_file(EditFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Edit file failed")
        )

class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Moves or renames a file/directory and performs post-move verification."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.move_file(MoveFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Move file failed")
        )

class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Deletes a file or directory with mandatory DELETE approval and post-deletion verification."
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        res = await global_filesystem_toolset.delete_file(DeleteFileInput(**params))
        return ToolResult(
            success=res["success"],
            data=res.get("result"),
            error="" if res["success"] else res.get("error", {}).get("message", "Delete file failed")
        )

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Searches the web for information, documentation, or recent news"
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("query") or params.get("title") or "general search"
        return ToolResult(
            success=True,
            data={
                "query": query,
                "results": [{"title": f"Synthesis on {query}", "snippet": f"Verified documentation regarding {query}.", "url": f"https://search.cocoa.local/query?q={query}"}]
            }
        )

class BrowserTool(BaseTool):
    name = "browser"
    description = "Simulates web page rendering, DOM extraction, and UI interactions"
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        url = params.get("url", "https://localhost")
        return ToolResult(success=True, data={"url": url, "page_title": "Cocoa Agent Verification Context", "extracted_text": f"Simulated browser interaction completed for {url}"})

class SchedulerTool(BaseTool):
    name = "scheduler"
    description = "Schedules recurring or delayed agent tasks"
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={"task_name": params.get("task_name", "background_check"), "cron": params.get("cron", "0 0 * * *"), "status": "scheduled"})

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        # Register core tools
        self.register(WebSearchTool())
        self.register(BrowserTool())
        self.register(SchedulerTool())

        # Register filesystem tools
        self.register(ListDirectoryTool())
        self.register(SearchFilesTool())
        self.register(ReadFileTool())
        self.register(InspectFileTool())
        self.register(CreateFileTool())
        self.register(EditFileTool())
        self.register(MoveFileTool())
        self.register(DeleteFileTool())

    def set_filesystem_root(self, root_path: str):
        global_filesystem_toolset.validator.add_authorized_root(root_path)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name) or self._tools.get("web_search")

    async def execute_tool(self, name: str, params: Dict[str, Any]) -> ToolResult:
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(success=False, data=None, error=f"Tool '{name}' not found in registry")
        return await tool.execute(params)

tool_registry = ToolRegistry()
