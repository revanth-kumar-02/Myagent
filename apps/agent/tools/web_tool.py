"""tools.web_tool — Web Search Tool (wraps ResearchRouter for real tool-based DuckDuckGo research)."""

from __future__ import annotations

from typing import Any
import structlog

from research.router import ResearchRouter
from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult

logger = structlog.get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo for live facts and external updates."""

    @property
    def tool_id(self) -> str:
        return "web_search"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB

    @property
    def description(self) -> str:
        return (
            "Search the web using DuckDuckGo for current information, news, documentation, "
            "or live repository/website updates. Returns real search snippets and URLs."
        )

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results to return", "default": 5},
            },
            "required": ["query"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "query": {"type": "string"},
                "count": {"type": "integer"},
            },
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return self._make_result(error="Parameter 'query' cannot be empty.")

        max_results = int(params.get("max_results", 5))
        try:
            router = ResearchRouter()
            response = await router.search(query=query, max_results=max_results)
            results_data = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                }
                for r in getattr(response, "results", [])
            ]
            return self._make_result(
                output={
                    "query": query,
                    "count": len(results_data),
                    "results": results_data,
                }
            )
        except Exception as e:
            logger.error("web_search_tool_failed", query=query, error=str(e))
            return self._make_result(error=f"Web search error: {str(e)}")
