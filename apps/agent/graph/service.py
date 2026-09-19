"""
graph.service — Unified Knowledge Graph Service Facade (V11).

Single entry point for all Knowledge Graph workflows:
  - Multi-source indexing (Code, Documents, Memory, Web Research, Tasks)
  - Automatic change detection & stale relationship pruning
  - Cross-source link discovery and semantic inference
  - Contradiction detection
  - Graph-assisted context generation for Agent & RAG
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.types import GraphEvidence
from graph.builder import RelationshipBuilder
from graph.extractor import EntityExtractor
from graph.retriever import GraphRetriever
from graph.store import GraphStore
from graph.types import (
    FormattedGraphContext,
    GraphEntityRecord,
    GraphQueryResult,
    GraphRelationshipRecord,
    GraphSubGraph,
)

logger = structlog.get_logger(__name__)


class KnowledgeGraphService:
    """
    Coordinates entity extraction, relationship synthesis, PostgreSQL graph storage, and retrieval.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        store: GraphStore | None = None,
        extractor: EntityExtractor | None = None,
        builder: RelationshipBuilder | None = None,
    ) -> None:
        self.store = store or GraphStore(db_session=db_session)
        self.extractor = extractor or EntityExtractor()
        self.builder = builder or RelationshipBuilder()
        self.retriever = GraphRetriever(store=self.store, extractor=self.extractor)

    # ── Indexing Workflows ───────────────────────────────────────────────────

    async def index_code_file(
        self,
        content: str,
        file_path: str,
        project_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[int, int]:
        """
        Prunes stale file graph, extracts code AST symbols and imports, and connects to graph.
        Returns: (entities_added_count, relationships_added_count)
        """
        # 1. Stale entity cleanup for modified file
        await self.cleanup_file(file_path, project_id=project_id)

        # 2. Extract entities and base AST relationships
        entities, relationships = self.extractor.extract_from_code(
            content=content,
            file_path=file_path,
            project_id=project_id,
            metadata=metadata,
        )

        # 3. Derive cross-source links with existing project entities
        existing_entities = list(self.store._entities.values())
        cross_links = self.builder.build_cross_source_links(
            entities=existing_entities + entities,
            project_id=project_id,
        )
        inferred_links = self.builder.infer_semantic_links(
            entities=existing_entities + entities,
            relationships=relationships + cross_links,
            project_id=project_id,
        )

        # 4. Store in graph
        await self.store.upsert_entities(entities)
        all_rels = relationships + cross_links + inferred_links
        await self.store.upsert_relationships(all_rels)

        logger.info(
            "knowledge_graph_code_indexed",
            file_path=file_path,
            entities=len(entities),
            relationships=len(all_rels),
        )
        return len(entities), len(all_rels)

    async def index_document_file(
        self,
        content: str,
        file_path: str,
        project_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[int, int]:
        """
        Prunes stale doc graph, extracts document sections, concepts, and mentions.
        """
        await self.cleanup_file(file_path, project_id=project_id)

        entities, relationships = self.extractor.extract_from_document(
            content=content,
            file_path=file_path,
            project_id=project_id,
            metadata=metadata,
        )

        existing_entities = list(self.store._entities.values())
        cross_links = self.builder.build_cross_source_links(
            entities=existing_entities + entities,
            project_id=project_id,
        )

        await self.store.upsert_entities(entities)
        all_rels = relationships + cross_links
        await self.store.upsert_relationships(all_rels)

        logger.info(
            "knowledge_graph_document_indexed",
            file_path=file_path,
            entities=len(entities),
            relationships=len(all_rels),
        )
        return len(entities), len(all_rels)

    async def index_memory(
        self,
        content: str,
        memory_type: str,
        memory_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
        source: str = "user_explicit",
    ) -> tuple[int, int]:
        """
        Index long-term memory into Knowledge Graph and detect contradictions.
        """
        # Clean existing source records for memory_id
        await self.store.cleanup_source_graph(f"memory:{memory_id}", project_id=project_id)

        entities, relationships = self.extractor.extract_from_memory(
            memory_content=content,
            memory_type=memory_type,
            memory_id=memory_id,
            project_id=project_id,
            source=source,
        )

        existing_entities = list(self.store._entities.values())
        cross_links = self.builder.build_cross_source_links(
            entities=existing_entities + entities,
            project_id=project_id,
        )
        contradictions = self.builder.detect_contradictions(
            entities=existing_entities + entities,
            project_id=project_id,
        )

        await self.store.upsert_entities(entities)
        all_rels = relationships + cross_links + contradictions
        await self.store.upsert_relationships(all_rels)

        return len(entities), len(all_rels)

    async def index_web_source(
        self,
        url: str,
        title: str,
        snippet: str,
        domain: str = "",
        project_id: uuid.UUID | None = None,
    ) -> tuple[int, int]:
        """
        Index DuckDuckGo web research result into Knowledge Graph.
        """
        entities, relationships = self.extractor.extract_from_web_source(
            url=url,
            title=title,
            snippet=snippet,
            domain=domain,
            project_id=project_id,
        )

        existing_entities = list(self.store._entities.values())
        cross_links = self.builder.build_cross_source_links(
            entities=existing_entities + entities,
            project_id=project_id,
        )

        await self.store.upsert_entities(entities)
        all_rels = relationships + cross_links
        await self.store.upsert_relationships(all_rels)

        return len(entities), len(all_rels)

    async def index_task(
        self,
        task_id: uuid.UUID,
        goal: str,
        tool_names: list[str] | None = None,
        dependencies: list[Any] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> tuple[int, int]:
        """
        Index autonomous task into Knowledge Graph.
        """
        await self.store.cleanup_source_graph(f"task:{task_id}", project_id=project_id)

        entities, relationships = self.extractor.extract_from_task(
            task_id=task_id,
            goal=goal,
            tool_names=tool_names,
            dependencies=dependencies,
            project_id=project_id,
        )

        existing_entities = list(self.store._entities.values())
        cross_links = self.builder.build_cross_source_links(
            entities=existing_entities + entities,
            project_id=project_id,
        )

        await self.store.upsert_entities(entities)
        all_rels = relationships + cross_links
        await self.store.upsert_relationships(all_rels)

        return len(entities), len(all_rels)

    # ── Maintenance & Cleanup ────────────────────────────────────────────────

    async def cleanup_file(self, file_path: str, project_id: uuid.UUID | None = None) -> int:
        """
        Remove all entities and relationships originating from a modified/deleted file.
        """
        source_tag = f"file:{file_path}"
        return await self.store.cleanup_source_graph(source_tag, project_id=project_id)

    # ── Retrieval & Query ────────────────────────────────────────────────────

    async def query_graph(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_depth: int = 2,
    ) -> GraphQueryResult:
        """Query Knowledge Graph subgraph around query keywords."""
        return await self.retriever.query_subgraph(query, project_id=project_id, max_depth=max_depth)

    async def get_graph_evidence(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
    ) -> list[GraphEvidence]:
        """Get structured GraphEvidence for context assembly."""
        return await self.retriever.get_graph_evidence(query, project_id=project_id)

    async def get_formatted_context(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_tokens: int = 1024,
    ) -> FormattedGraphContext:
        """Retrieve bounded Markdown graph context."""
        return await self.retriever.retrieve_formatted_context(
            query=query,
            project_id=project_id,
            max_tokens=max_tokens,
        )
