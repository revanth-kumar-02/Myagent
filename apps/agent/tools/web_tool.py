"""tools.web_tool — Web Search Tool (wraps ResearchRouter for tool-based invocation)."""
from __future__ import annotations
from typing import Any
from tools.base import BaseTool
from tools.types import ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web for current information not available in the project knowledge base. "
        "Results are kept completely separate from project RAG data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        raise NotImplementedError  # TODO: wire to ResearchRouter in feature phase
