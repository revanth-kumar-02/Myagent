"""
tests.test_knowledge_graph_v11 — Test Suite for Kora Knowledge Graph & Cross-Source Intelligence (V11).

Covers:
  1. Entity Layer: creation, canonical normalization, metadata, all 10 EntityTypes
  2. Relationship Layer: creation, provenance, inference flagging, all 10 RelationshipTypes
  3. Graph Storage & Traversal: CRUD, BFS subgraphs, pathfinding, cycle handling
  4. Project Isolation: strict partition between projects
  5. Source Updates & Stale Cleanup: cleanup on file/source modification
  6. Extraction & Synthesis: Code AST, Document Intelligence, Long-Term Memory, Web Research, Tasks
  7. Cross-Source Linking & Contradiction Detection: connecting heterogeneous sources
  8. Graph-Assisted Retrieval: seed discovery, subgraph expansion, bounded formatting
  9. Context Packaging & Agent Integration: ContextPackageBuilder & ContextResolver integration
"""

from __future__ import annotations

import uuid
import pytest

from core.context_package import ContextPackageBuilder
from core.context_resolver import ContextResolver
from core.types import AgentContextPackage, GraphEvidence, SourceType
from graph.builder import RelationshipBuilder
from graph.extractor import EntityExtractor
from graph.retriever import GraphRetriever
from graph.service import KnowledgeGraphService
from graph.store import GraphStore
from graph.types import (
    EntityType,
    GraphEntityRecord,
    GraphQuery,
    GraphRelationshipRecord,
    RelationshipType,
    normalize_entity_name,
)


# ── 1. Entity Layer Tests ─────────────────────────────────────────────────────

class TestEntityLayer:
    """Verify entity creation, typing, canonical naming, and representation."""

    def test_all_entity_types_supported(self) -> None:
        expected_types = [
            "person", "project", "organization", "file", "document",
            "code_symbol", "task", "technology", "concept", "web_source"
        ]
        for et in expected_types:
            enum_val = EntityType(et)
            assert enum_val.value == et

    def test_entity_creation_and_canonical_normalization(self) -> None:
        ent = GraphEntityRecord(
            name="  PostgreSQL Database ",
            entity_type=EntityType.TECHNOLOGY,
            source="memory:config",
            confidence=0.95,
        )
        assert ent.canonical_name == "postgresql database"
        assert ent.entity_type == EntityType.TECHNOLOGY
        assert ent.confidence == 0.95
        assert isinstance(ent.entity_id, uuid.UUID)

    def test_entity_metadata_storage(self) -> None:
        file_id = uuid.uuid4()
        ent = GraphEntityRecord(
            name="session.py",
            entity_type=EntityType.FILE,
            source=f"file:{file_id}",
            metadata={"path": "apps/agent/core/session.py", "lines": 200},
        )
        assert ent.metadata["lines"] == 200
        assert ent.metadata["path"] == "apps/agent/core/session.py"


# ── 2. Relationship Layer Tests ───────────────────────────────────────────────

class TestRelationshipLayer:
    """Verify relationship creation, types, provenance, and inferred status."""

    def test_all_relationship_types_supported(self) -> None:
        expected_types = [
            "belongs_to", "references", "depends_on", "created_by", "related_to",
            "contains", "implements", "uses", "derived_from", "contradicts"
        ]
        for rt in expected_types:
            enum_val = RelationshipType(rt)
            assert enum_val.value == rt

    def test_relationship_provenance_and_inferred_flag(self) -> None:
        e1_id = uuid.uuid4()
        e2_id = uuid.uuid4()
        rel = GraphRelationshipRecord(
            source_entity_id=e1_id,
            relationship_type=RelationshipType.DEPENDS_ON,
            target_entity_id=e2_id,
            confidence=0.88,
            provenance={"source_type": "import_ast", "file_path": "main.py"},
            is_inferred=False,
        )
        assert rel.is_inferred is False
        assert rel.confidence == 0.88
        assert rel.provenance["file_path"] == "main.py"

        inferred_rel = GraphRelationshipRecord(
            source_entity_id=e1_id,
            relationship_type=RelationshipType.RELATED_TO,
            target_entity_id=e2_id,
            confidence=0.65,
            provenance={"source_type": "semantic_inference"},
            is_inferred=True,
        )
        assert inferred_rel.is_inferred is True


# ── 3. Graph Store & Traversal Tests ──────────────────────────────────────────

class TestGraphStoreAndTraversal:
    """Verify storage CRUD, BFS subgraph extraction, pathfinding, and cycle safety."""

    @pytest.mark.asyncio
    async def test_crud_and_adjacency(self) -> None:
        store = GraphStore()

        e1 = GraphEntityRecord(name="AuthService", entity_type=EntityType.CODE_SYMBOL, source="file:auth.py")
        e2 = GraphEntityRecord(name="Database", entity_type=EntityType.TECHNOLOGY, source="file:auth.py")
        await store.upsert_entities([e1, e2])

        rel = GraphRelationshipRecord(
            source_entity_id=e1.entity_id,
            relationship_type=RelationshipType.USES,
            target_entity_id=e2.entity_id,
        )
        await store.upsert_relationship(rel)

        # Retrieve entity
        fetched = await store.get_entity(e1.entity_id)
        assert fetched is not None
        assert fetched.name == "AuthService"

        # Check relationships
        rels_out = await store.get_relationships_for_entity(e1.entity_id, direction="out")
        assert len(rels_out) == 1
        assert rels_out[0].target_entity_id == e2.entity_id

        rels_in = await store.get_relationships_for_entity(e2.entity_id, direction="in")
        assert len(rels_in) == 1
        assert rels_in[0].source_entity_id == e1.entity_id

    @pytest.mark.asyncio
    async def test_bfs_subgraph_traversal_with_depth_limit(self) -> None:
        store = GraphStore()
        # Create chain: A -> B -> C -> D
        a = GraphEntityRecord(name="A", entity_type=EntityType.FILE, source="s:1")
        b = GraphEntityRecord(name="B", entity_type=EntityType.CODE_SYMBOL, source="s:2")
        c = GraphEntityRecord(name="C", entity_type=EntityType.TECHNOLOGY, source="s:3")
        d = GraphEntityRecord(name="D", entity_type=EntityType.CONCEPT, source="s:4")
        await store.upsert_entities([a, b, c, d])

        r1 = GraphRelationshipRecord(source_entity_id=a.entity_id, relationship_type=RelationshipType.CONTAINS, target_entity_id=b.entity_id)
        r2 = GraphRelationshipRecord(source_entity_id=b.entity_id, relationship_type=RelationshipType.USES, target_entity_id=c.entity_id)
        r3 = GraphRelationshipRecord(source_entity_id=c.entity_id, relationship_type=RelationshipType.RELATED_TO, target_entity_id=d.entity_id)
        await store.upsert_relationships([r1, r2, r3])

        # Depth 1 from A -> should include A, B, and r1
        sub1 = await store.get_subgraph([a.entity_id], max_depth=1)
        assert len(sub1.entities) == 2
        assert len(sub1.relationships) == 1

        # Depth 2 from A -> should include A, B, C, and r1, r2
        sub2 = await store.get_subgraph([a.entity_id], max_depth=2)
        assert len(sub2.entities) == 3
        assert len(sub2.relationships) == 2

    @pytest.mark.asyncio
    async def test_pathfinding_between_entities(self) -> None:
        store = GraphStore()
        e1 = GraphEntityRecord(name="LoginController", entity_type=EntityType.CODE_SYMBOL, source="s:1")
        e2 = GraphEntityRecord(name="JwtUtil", entity_type=EntityType.CODE_SYMBOL, source="s:2")
        e3 = GraphEntityRecord(name="Cryptography", entity_type=EntityType.TECHNOLOGY, source="s:3")
        await store.upsert_entities([e1, e2, e3])

        r1 = GraphRelationshipRecord(source_entity_id=e1.entity_id, relationship_type=RelationshipType.USES, target_entity_id=e2.entity_id, confidence=0.9)
        r2 = GraphRelationshipRecord(source_entity_id=e2.entity_id, relationship_type=RelationshipType.DEPENDS_ON, target_entity_id=e3.entity_id, confidence=0.8)
        await store.upsert_relationships([r1, r2])

        paths = await store.find_paths(source_id=e1.entity_id, target_id=e3.entity_id, max_depth=3)
        assert len(paths) == 1
        assert [e.name for e in paths[0].entities] == ["LoginController", "JwtUtil", "Cryptography"]
        assert paths[0].confidence == pytest.approx(0.72, abs=1e-2)


# ── 4. Project Isolation Tests ────────────────────────────────────────────────

class TestProjectIsolation:
    """Verify that project boundaries prevent data leakage across projects."""

    @pytest.mark.asyncio
    async def test_project_entities_isolated(self) -> None:
        store = GraphStore()
        proj_a = uuid.uuid4()
        proj_b = uuid.uuid4()

        ent_a = GraphEntityRecord(name="SecretModuleA", entity_type=EntityType.FILE, source="file:a.py", project_id=proj_a)
        ent_b = GraphEntityRecord(name="SecretModuleB", entity_type=EntityType.FILE, source="file:b.py", project_id=proj_b)
        ent_global = GraphEntityRecord(name="Python", entity_type=EntityType.TECHNOLOGY, source="global", project_id=None)

        await store.upsert_entities([ent_a, ent_b, ent_global])

        # Query project A -> must not return SecretModuleB
        results_a = await store.find_entities(project_id=proj_a)
        names_a = [e.name for e in results_a]
        assert "SecretModuleA" in names_a
        assert "Python" in names_a
        assert "SecretModuleB" not in names_a

        # Query project B -> must not return SecretModuleA
        results_b = await store.find_entities(project_id=proj_b)
        names_b = [e.name for e in results_b]
        assert "SecretModuleB" in names_b
        assert "SecretModuleA" not in names_b


# ── 5. Stale Relationship Cleanup Tests ───────────────────────────────────────

class TestStaleRelationshipCleanup:
    """Verify cleanup of obsolete entities and edges when source files change."""

    @pytest.mark.asyncio
    async def test_cleanup_file_source_entities_and_edges(self) -> None:
        store = GraphStore()
        file_path = "apps/agent/core/old_file.py"
        source_tag = f"file:{file_path}"

        e_file = GraphEntityRecord(name="old_file.py", entity_type=EntityType.FILE, source=source_tag)
        e_class = GraphEntityRecord(name="OldClass", entity_type=EntityType.CODE_SYMBOL, source=source_tag)
        e_tech = GraphEntityRecord(name="FastAPI", entity_type=EntityType.TECHNOLOGY, source="file:other.py")

        await store.upsert_entities([e_file, e_class, e_tech])

        r1 = GraphRelationshipRecord(source_entity_id=e_file.entity_id, relationship_type=RelationshipType.CONTAINS, target_entity_id=e_class.entity_id)
        r2 = GraphRelationshipRecord(source_entity_id=e_class.entity_id, relationship_type=RelationshipType.USES, target_entity_id=e_tech.entity_id)
        await store.upsert_relationships([r1, r2])

        # Clean up old_file.py
        deleted_count = await store.cleanup_source_graph(source_tag)
        assert deleted_count == 2  # e_file and e_class

        # Verify e_file and e_class are gone, but FastAPI remains
        assert await store.get_entity(e_file.entity_id) is None
        assert await store.get_entity(e_class.entity_id) is None
        assert await store.get_entity(e_tech.entity_id) is not None

        # Verify edges r1 and r2 are pruned from adjacency
        rels_tech = await store.get_relationships_for_entity(e_tech.entity_id, direction="in")
        assert len(rels_tech) == 0


# ── 6. Extraction & Cross-Source Linking Tests ────────────────────────────────

class TestExtractionAndCrossSourceLinking:
    """Verify multi-source entity and relationship extraction."""

    def test_extract_from_code_ast(self) -> None:
        extractor = EntityExtractor()
        code = """
import sqlalchemy
from fastapi import FastAPI
import pytest

class AgentSession(BaseModel):
    def __init__(self):
        pass

    async def execute_query(self, query: str):
        return True
"""
        entities, relationships = extractor.extract_from_code(code, "apps/agent/core/session.py")

        entity_names = {e.name for e in entities}
        assert "session.py" in entity_names
        assert "AgentSession" in entity_names
        assert "execute_query" in entity_names
        assert "sqlalchemy" in entity_names
        assert "fastapi" in entity_names

        # Check relationships
        rel_types = {r.relationship_type for r in relationships}
        assert RelationshipType.CONTAINS in rel_types
        assert RelationshipType.BELONGS_TO in rel_types
        assert RelationshipType.USES in rel_types

    def test_extract_from_document(self) -> None:
        extractor = EntityExtractor()
        doc_md = """# Architecture Overview
This system uses PostgreSQL and pgvector for semantic retrieval.
## Database Design
Tables are normalized.
"""
        entities, relationships = extractor.extract_from_document(doc_md, "docs/architecture.md")
        names = {e.name for e in entities}
        assert "architecture.md" in names
        assert "Architecture Overview" in names
        assert "Database Design" in names
        assert "postgresql" in names
        assert "pgvector" in names

    def test_extract_from_memory(self) -> None:
        extractor = EntityExtractor()
        mem_id = uuid.uuid4()
        content = "User prefers using PostgreSQL over SQLite for all persistent storage."
        entities, relationships = extractor.extract_from_memory(content, "user_preference", mem_id)

        names = {e.name for e in entities}
        assert "User" in names
        assert "postgresql" in names
        assert "sqlite" in names

    def test_extract_from_web_source(self) -> None:
        extractor = EntityExtractor()
        entities, relationships = extractor.extract_from_web_source(
            url="https://docs.python.org/3/library/asyncio.html",
            title="AsyncIO in Python",
            snippet="Asynchronous I/O, event loop, and coroutines in Python.",
            domain="docs.python.org",
        )
        names = {e.name for e in entities}
        assert "AsyncIO in Python" in names
        assert "python" in names

    def test_extract_from_task(self) -> None:
        extractor = EntityExtractor()
        task_id = uuid.uuid4()
        entities, relationships = extractor.extract_from_task(
            task_id=task_id,
            goal="Refactor RAG Pipeline",
            tool_names=["file_writer", "terminal"],
        )
        names = {e.name for e in entities}
        assert "Refactor RAG Pipeline" in names
        assert "file_writer" in names
        assert "terminal" in names

    def test_contradiction_detection(self) -> None:
        builder = RelationshipBuilder()
        doc_concept = GraphEntityRecord(
            name="Database Policy",
            entity_type=EntityType.CONCEPT,
            source="docs:policy",
            metadata={"full_content": "Never use SQLite in production deployments."},
        )
        tech_sqlite = GraphEntityRecord(
            name="sqlite",
            entity_type=EntityType.TECHNOLOGY,
            source="file:settings.py",
        )

        contradictions = builder.detect_contradictions([doc_concept, tech_sqlite])
        assert len(contradictions) == 1
        assert contradictions[0].relationship_type == RelationshipType.CONTRADICTS
        assert contradictions[0].target_entity_id == tech_sqlite.entity_id


# ── 7. Knowledge Graph Service & Retrieval Tests ──────────────────────────────

class TestKnowledgeGraphService:
    """Verify high-level service indexing, queries, and graph-assisted retrieval."""

    @pytest.mark.asyncio
    async def test_service_indexing_and_subgraph_query(self) -> None:
        service = KnowledgeGraphService()
        project_id = uuid.uuid4()

        code = """
class QueryEngine:
    def execute(self):
        pass
"""
        # 1. Index Code File
        ents_added, rels_added = await service.index_code_file(code, "engine.py", project_id=project_id)
        assert ents_added > 0
        assert rels_added > 0

        # 2. Index Memory referencing QueryEngine
        mem_id = uuid.uuid4()
        await service.index_memory("User wants QueryEngine optimized for latency", "task_context", mem_id, project_id=project_id)

        # 3. Query Knowledge Graph
        query_result = await service.query_graph("How does QueryEngine work?", project_id=project_id)
        assert query_result.total_entities >= 2

        # 4. Extract Structured Evidence
        evidence = await service.get_graph_evidence("QueryEngine", project_id=project_id)
        assert len(evidence) > 0
        assert any(ev.source_entity == "QueryEngine" or ev.target_entity == "QueryEngine" for ev in evidence)

        # 5. Get Formatted Context Block
        formatted = await service.get_formatted_context("QueryEngine", project_id=project_id)
        assert formatted.token_count > 0
        assert "Verified Relationships" in formatted.text or "Inferred" in formatted.text


# ── 8. Agent Context Package & Resolver Integration ───────────────────────────

class TestAgentContextAndResolverIntegration:
    """Verify ContextPackageBuilder formats graph evidence and ContextResolver routes queries."""

    def test_context_package_builder_with_graph_evidence(self) -> None:
        builder = ContextPackageBuilder()

        ev_verified = GraphEvidence(
            source_entity="session.py",
            relationship_type="contains",
            target_entity="SessionManager",
            confidence=1.0,
            provenance_source="file:session.py",
            is_inferred=False,
            evidence_text="file contains class",
        )
        ev_inferred = GraphEvidence(
            source_entity="SessionManager",
            relationship_type="uses",
            target_entity="PostgreSQL",
            confidence=0.8,
            provenance_source="transitive",
            is_inferred=True,
            evidence_text="inferred from imports",
        )

        package = builder.assemble(graph_evidence=[ev_verified, ev_inferred])
        assert SourceType.GRAPH in package.resolved_sources
        assert len(package.graph_evidence) == 2
        assert "=== [GRAPH] Cross-Source Knowledge Graph" in package.formatted_text
        assert "[VERIFIED] session.py —[CONTAINS]→ SessionManager" in package.formatted_text
        assert "[INFERRED] SessionManager —[USES]→ PostgreSQL" in package.formatted_text

    def test_context_resolver_routes_graph_queries(self) -> None:
        resolver = ContextResolver()

        # Questions about architecture, dependencies, or relationships should trigger GRAPH
        sources = resolver.resolve("What are the dependencies of the storage engine?")
        assert SourceType.GRAPH in sources
        assert SourceType.RAG in sources

        sources_rel = resolver.resolve("Show me the class hierarchy and relationships between models")
        assert SourceType.GRAPH in sources_rel

        # Normal conversational queries should not trigger GRAPH
        sources_conv = resolver.resolve("Hello, how are you today?")
        assert len(sources_conv) == 0
