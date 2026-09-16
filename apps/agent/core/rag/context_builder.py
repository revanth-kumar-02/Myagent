import os
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field
from core.rag.retriever import project_rag_retriever, SearchResultChunk

class BoundedProjectChunk(BaseModel):
    file: str
    path: str
    language: str
    symbol: Optional[str] = None
    relevance: float
    content: str

class ProjectContextResult(BaseModel):
    project_id: str
    query: str
    chunks: List[BoundedProjectChunk]
    total_chars: int
    formatted_context: str

class WebContextItem(BaseModel):
    title: str
    url: str
    domain: Optional[str] = None
    relevance: float = 0.8
    snippet: str
    published_date: Optional[str] = None

class UnifiedAgentContext(BaseModel):
    project_id: Optional[str] = None
    query: str
    project_chunks: List[BoundedProjectChunk] = Field(default_factory=list)
    web_items: List[WebContextItem] = Field(default_factory=list)
    formatted_prompt_context: str

class ProjectRagContextBuilder:
    """
    Constructs bounded project context from highest-relevance structural chunks.
    Enforces token/char limits and eliminates duplicates.
    """

    def __init__(self, retriever=None):
        self.retriever = retriever or project_rag_retriever

    async def build_project_context(
        self,
        project_id: str,
        query: str,
        max_chars: int = 12000,
        max_chunks: int = 8
    ) -> ProjectContextResult:
        if not project_id or not query:
            return ProjectContextResult(
                project_id=project_id or "",
                query=query or "",
                chunks=[],
                total_chars=0,
                formatted_context=""
            )

        raw_chunks = await self.retriever.search(
            query=query,
            project_id=project_id,
            limit=max_chunks * 2
        )

        seen_keys: Set[str] = set()
        bounded_chunks: List[BoundedProjectChunk] = []
        current_chars = 0
        context_blocks: List[str] = []

        for c in raw_chunks:
            dedup_key = f"{c.file_path}::{c.chunk_index}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            chunk_len = len(c.content)
            if current_chars + chunk_len > max_chars and bounded_chunks:
                break

            fname = os.path.basename(c.file_path)
            b_chunk = BoundedProjectChunk(
                file=fname,
                path=c.file_path,
                language=c.language,
                symbol=c.symbol,
                relevance=c.relevance,
                content=c.content
            )
            bounded_chunks.append(b_chunk)

            block = (
                f"### [PROJECT] {c.file_path} "
                f"(symbol: {c.symbol or 'top-level'}, relevance: {c.relevance:.2f})\n"
                f"```{c.language}\n"
                f"{c.content}\n"
                f"```"
            )
            context_blocks.append(block)
            current_chars += len(block)

            if len(bounded_chunks) >= max_chunks:
                break

        formatted = "\n\n".join(context_blocks)
        return ProjectContextResult(
            project_id=project_id,
            query=query,
            chunks=bounded_chunks,
            total_chars=len(formatted),
            formatted_context=formatted
        )

class UnifiedAgentContextBuilder:
    """
    Assembles unified context combining PROJECT_CONTEXT and WEB_CONTEXT
    with strict source provenance preservation.
    """

    def __init__(self, rag_builder: Optional[ProjectRagContextBuilder] = None):
        self.rag_builder = rag_builder or ProjectRagContextBuilder()

    async def build_unified_context(
        self,
        query: str,
        project_id: Optional[str] = None,
        web_sources: Optional[List[Any]] = None,
        max_chars: int = 16000
    ) -> UnifiedAgentContext:
        proj_result = None
        if project_id:
            proj_result = await self.rag_builder.build_project_context(
                project_id=project_id,
                query=query,
                max_chars=int(max_chars * 0.65)
            )

        web_items: List[WebContextItem] = []
        if web_sources:
            for s in web_sources:
                if hasattr(s, "url"):
                    title = getattr(s, "title", "Web Source")
                    url = getattr(s, "url", "")
                    domain = getattr(s, "domain", None)
                    relevance = float(getattr(s, "relevance", 0.8) or 0.8)
                    snippet = getattr(s, "content_excerpt", "") or getattr(s, "snippet", "")
                    pub_date = getattr(s, "published_date", None)
                    web_items.append(
                        WebContextItem(
                            title=title,
                            url=url,
                            domain=domain,
                            relevance=round(relevance, 2),
                            snippet=snippet[:500],
                            published_date=pub_date
                        )
                    )
                elif isinstance(s, dict):
                    web_items.append(
                        WebContextItem(
                            title=s.get("title", "Web Source"),
                            url=s.get("url", ""),
                            domain=s.get("domain"),
                            relevance=float(s.get("relevance", 0.8)),
                            snippet=(s.get("content_excerpt") or s.get("snippet") or "")[:500],
                            published_date=s.get("published_date")
                        )
                    )

        sections: List[str] = []

        if proj_result and proj_result.chunks:
            sections.append(
                "==== PROJECT CONTEXT (LOCAL PROJECT KNOWLEDGE) ====\n"
                "The following code and documentation sections were retrieved from the local workspace repository:\n\n"
                + proj_result.formatted_context
            )

        if web_items:
            web_lines = []
            for w in web_items:
                date_str = f"\n  Published: {w.published_date}" if w.published_date else ""
                web_lines.append(
                    f"- [{w.title}]({w.url})\n"
                    f"  Source Domain: {w.domain or w.url}\n"
                    f"  Relevance: {w.relevance:.2f}"
                    f"{date_str}\n"
                    f"  Excerpt: {w.snippet.strip()}"
                )
            sections.append(
                "==== WEB RESEARCH CONTEXT (LIVE EXTERNAL SOURCES) ====\n"
                "The following live web references were retrieved via external search:\n\n"
                + "\n\n".join(web_lines)
            )

        formatted_all = "\n\n".join(sections)

        return UnifiedAgentContext(
            project_id=project_id,
            query=query,
            project_chunks=proj_result.chunks if proj_result else [],
            web_items=web_items,
            formatted_prompt_context=formatted_all
        )

project_context_builder = ProjectRagContextBuilder()
unified_agent_context_builder = UnifiedAgentContextBuilder()
