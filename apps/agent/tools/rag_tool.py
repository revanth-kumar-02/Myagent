"""tools.rag_tool — RAG Query Tool (wraps RAGEngine for tool-based invocation)."""
from __future__ import annotations
from typing import Any
from tools.base import BaseTool
from tools.types import ToolResult


class RAGQueryTool(BaseTool):
    name = "rag_query"
    description = (
        "Search the indexed project knowledge base for information relevant to the query. "
        "Use this when you need to look up project-specific code, documentation, or files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "top_k": {"type": "integer", "default": 8},
            "metadata_filter": {
                "type": "object",
                "description": "Optional filter on chunk metadata (e.g. file_type, language)",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        raise NotImplementedError  # TODO: wire to RAGRetriever + Reranker + ContextBuilder
