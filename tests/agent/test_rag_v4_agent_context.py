"""
tests.agent.test_rag_v4_agent_context — Comprehensive RAG V4 Agent Context Tests

Covers:
  1. Context Resolver & Retrieval Routing (RAG, Memory, Web, Mixed, None)
  2. Multi-Source Context Assembly (ContextPackageBuilder)
  3. Deterministic Context & Token Budget Limits
  4. Grounded Context Formatting & Provenance Survival
  5. ContextManager Token Budget & Oldest-First History Truncation
  6. Context-Aware Planner Step Generation
  7. Missing Context Resilience & Project Isolation
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.context import ContextManager
from core.context_package import ContextPackageBuilder
from core.context_resolver import ContextResolver
from core.planner import Planner
from core.types import (
    ActionType,
    ChatRequest,
    ContextItem,
    SourceType,
)
from rag.types import (
    Chunk,
    DocumentType,
    RetrievedChunk,
)


class TestContextResolverRouting:
    def test_project_questions_route_to_rag(self) -> None:
        resolver = ContextResolver()
        project_id = uuid.uuid4()

        queries = [
            "Where is the authenticateUser function defined?",
            "What does main.py do?",
            "Show me the database schema in models.py",
            "Which sheet has the revenue table in financials.xlsx?",
            "Find the slide about system architecture in deck.pptx",
        ]

        for q in queries:
            sources = resolver.resolve(q, project_id=project_id)
            assert SourceType.RAG in sources, f"Query '{q}' failed to route to RAG"
            assert SourceType.WEB not in sources

    def test_personal_preference_questions_route_to_memory(self) -> None:
        resolver = ContextResolver()

        queries = [
            "What is my preferred coding style?",
            "Remember that I like TypeScript over JavaScript",
            "Did I mention my favorite theme?",
            "What are my settings for deployment?",
        ]

        for q in queries:
            sources = resolver.resolve(q)
            assert SourceType.MEMORY in sources, f"Query '{q}' failed to route to Memory"

    def test_current_external_questions_route_to_web(self) -> None:
        resolver = ContextResolver()

        queries = [
            "Search the web for the latest Python 3.14 release notes",
            "What is the weather in Tokyo today?",
            "Look up on google what is new in Flutter 2026",
            "Check the current price of gold online",
            "https://docs.anthropic.com/en/docs/overview",
        ]

        for q in queries:
            sources = resolver.resolve(q)
            assert SourceType.WEB in sources, f"Query '{q}' failed to route to Web"

    def test_mixed_questions_combine_sources(self) -> None:
        resolver = ContextResolver()
        project_id = uuid.uuid4()

        mixed_query = "Compare our local database schema in models.py with the latest online PostgreSQL 18 best practices"
        sources = resolver.resolve(mixed_query, project_id=project_id)
        assert SourceType.RAG in sources
        assert SourceType.WEB in sources

    def test_conversational_questions_bypass_retrieval(self) -> None:
        resolver = ContextResolver()
        project_id = uuid.uuid4()

        queries = [
            "Hello",
            "Good morning!",
            "Thanks a lot",
            "What is 2 + 2?",
            "Tell me a joke",
        ]

        for q in queries:
            sources = resolver.resolve(q, project_id=project_id)
            assert len(sources) == 0, f"Conversational query '{q}' triggered unnecessary retrieval: {sources}"


class TestMultiSourceContextAssembly:
    def test_assemble_multi_source_package(self) -> None:
        builder = ContextPackageBuilder()
        project_id = uuid.uuid4()

        # 1. RAG Chunks
        c1 = Chunk(
            chunk_index=0,
            content="class DatabaseService { async connect() {} }",
            doc_type=DocumentType.CODE,
            file_path="src/db.ts",
            project_id=project_id,
            metadata={"start_line": 10, "end_line": 25, "symbol": "DatabaseService"},
        )
        rc1 = RetrievedChunk(chunk=c1, combined_score=0.95)

        # 2. Memory Entry
        mock_mem = MagicMock()
        mock_mem.content = "User prefers async/await over raw Promises."
        mock_mem.type = "preference"
        mock_mem.score = 1.0

        # 3. Web Result
        web_res = {
            "title": "TypeScript Best Practices",
            "url": "https://typescript.org/docs",
            "snippet": "Always use strongly typed interfaces for database connections.",
            "score": 0.85,
        }

        package = builder.assemble(
            rag_chunks=[rc1],
            memory_entries=[mock_mem],
            web_results=[web_res],
        )

        assert len(package.items) == 3
        assert len(package.rag_sources) == 1
        assert len(package.web_sources) == 1
        assert package.rag_sources[0].file_path == "src/db.ts"
        assert package.rag_sources[0].symbol == "DatabaseService"
        assert package.web_sources[0].url == "https://typescript.org/docs"

        # Grounding sections check
        assert "=== [RAG] Verified Project Knowledge (High Confidence) ===" in package.formatted_text
        assert "=== [MEMORY] User Preferences & Persistent Context ===" in package.formatted_text
        assert "=== [WEB] External Web Research (Unverified / Live Data) ===" in package.formatted_text
        assert package.token_count > 0

    def test_deterministic_budget_limits(self) -> None:
        builder = ContextPackageBuilder(
            max_rag_chunks=2,
            max_memory_items=1,
            max_web_sources=1,
            max_total_tokens=5000,
        )
        project_id = uuid.uuid4()

        # Provide 5 RAG chunks
        rag_chunks = [
            RetrievedChunk(
                chunk=Chunk(
                    chunk_index=i,
                    content=f"Chunk {i} content",
                    doc_type=DocumentType.PLAIN,
                    file_path=f"file_{i}.txt",
                    project_id=project_id,
                )
            )
            for i in range(5)
        ]

        # Provide 3 memory entries
        memories = [MagicMock(content=f"Preference {i}", type="pref", score=1.0) for i in range(3)]

        # Provide 3 web results
        web_results = [{"title": f"Web {i}", "url": f"http://{i}.com", "snippet": f"Snippet {i}", "score": 0.5} for i in range(3)]

        package = builder.assemble(
            rag_chunks=rag_chunks,
            memory_entries=memories,
            web_results=web_results,
        )

        assert len(package.rag_sources) == 2  # capped at max_rag_chunks=2
        assert len(package.web_sources) == 1  # capped at max_web_sources=1
        assert len([item for item in package.items if item.source_type == SourceType.MEMORY]) == 1


class TestContextManagerAndHistoryTruncation:
    def test_context_manager_truncates_oldest_history_first(self) -> None:
        session_id = uuid.uuid4()
        project_id = uuid.uuid4()
        manager = ContextManager(session_id, project_id, token_budget=250)

        # Add 10 long messages
        for i in range(10):
            manager._history.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"Message number {i} with lots of additional text to take up budget."})

        window = manager.build(rag_context="Verified project code.")
        assert len(window.history) < 10
        # The newest message (number 9) must be preserved
        assert "Message number 9" in window.history[-1]["content"]
        assert window.token_used <= window.token_budget


class TestContextAwarePlanner:
    @pytest.mark.asyncio
    async def test_planner_creates_rag_step_for_project_request(self) -> None:
        planner = Planner()
        project_id = uuid.uuid4()
        req = ChatRequest(
            message="How is user authentication implemented in the backend?",
            session_id=uuid.uuid4(),
            project_id=project_id,
        )

        plan = await planner.plan(req)
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == ActionType.RAG_QUERY
        assert plan.steps[1].action_type == ActionType.MODEL_GENERATE

    @pytest.mark.asyncio
    async def test_planner_creates_direct_step_for_simple_request(self) -> None:
        planner = Planner()
        req = ChatRequest(
            message="Hello!",
            session_id=uuid.uuid4(),
            project_id=None,
        )

        plan = await planner.plan(req)
        assert len(plan.steps) == 1
        assert plan.steps[0].action_type == ActionType.MODEL_GENERATE


class TestMissingContextAndProjectIsolation:
    def test_missing_context_handled_cleanly(self) -> None:
        builder = ContextPackageBuilder()
        package = builder.assemble(
            rag_chunks=[],
            memory_entries=[],
            web_results=[],
        )
        assert len(package.items) == 0
        assert len(package.rag_sources) == 0
        assert len(package.web_sources) == 0
        assert package.formatted_text == ""
        assert package.token_count == 0

    def test_project_isolation_in_sources(self) -> None:
        project_a = uuid.uuid4()
        c_a = Chunk(
            chunk_index=0,
            content="Project A proprietary code",
            doc_type=DocumentType.CODE,
            file_path="secret.py",
            project_id=project_a,
        )
        rc_a = RetrievedChunk(chunk=c_a)

        builder = ContextPackageBuilder()
        package = builder.assemble(rag_chunks=[rc_a])
        assert len(package.rag_sources) == 1
        assert package.rag_sources[0].file_path == "secret.py"
        assert package.items[0].file_path == "secret.py"
