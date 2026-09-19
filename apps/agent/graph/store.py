"""
graph.store — PostgreSQL & In-Memory Graph Storage Subsystem (V11).

Provides persistence and graph traversal algorithms:
  - CRUD on GraphEntity and GraphRelationship models
  - PostgreSQL backing via async SQLAlchemy ORM
  - In-memory storage/cache fallback for ultra-fast traversal & unit tests
  - BFS/DFS Subgraph extraction with cycle prevention and depth bounds
  - Pathfinding across heterogeneous entities
  - Stale entity & relationship deletion upon file/chunk invalidation
  - Strict project isolation enforcement
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Sequence

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.schema import GraphEntity as DBGraphEntity, GraphRelationship as DBGraphRelationship
from graph.types import (
    EntityType,
    GraphEntityRecord,
    GraphPath,
    GraphRelationshipRecord,
    GraphSubGraph,
    RelationshipType,
    normalize_entity_name,
)

logger = structlog.get_logger(__name__)


class GraphStore:
    """
    Unified Graph Storage engine supporting PostgreSQL persistence and in-memory traversal caching.
    """

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self._db = db_session
        self._entities: dict[uuid.UUID, GraphEntityRecord] = {}
        self._relationships: dict[uuid.UUID, GraphRelationshipRecord] = {}
        # Secondary indexes for in-memory traversal speed
        self._outgoing_adj: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._incoming_adj: dict[uuid.UUID, set[uuid.UUID]] = {}

    # ── Entity Operations ─────────────────────────────────────────────────────

    async def upsert_entity(self, entity: GraphEntityRecord) -> GraphEntityRecord:
        """
        Insert or update a graph node in memory and PostgreSQL.
        """
        entity.updated_at = datetime.now(timezone.utc)
        self._entities[entity.entity_id] = entity

        if self._db is not None:
            try:
                db_ent = await self._db.get(DBGraphEntity, entity.entity_id)
                if db_ent is None:
                    db_ent = DBGraphEntity(
                        id=entity.entity_id,
                        entity_type=entity.entity_type.value,
                        name=entity.name,
                        canonical_name=entity.canonical_name,
                        project_id=entity.project_id,
                        source=entity.source,
                        confidence=entity.confidence,
                        metadata_=entity.metadata,
                    )
                    self._db.add(db_ent)
                else:
                    db_ent.name = entity.name
                    db_ent.canonical_name = entity.canonical_name
                    db_ent.confidence = entity.confidence
                    db_ent.metadata_ = entity.metadata
                    db_ent.updated_at = entity.updated_at
                await self._db.flush()
            except Exception as exc:
                logger.warning("graph_store_db_entity_upsert_failed", error=str(exc))

        return entity

    async def upsert_entities(self, entities: Sequence[GraphEntityRecord]) -> list[GraphEntityRecord]:
        """Batch upsert multiple entities."""
        results: list[GraphEntityRecord] = []
        for ent in entities:
            res = await self.upsert_entity(ent)
            results.append(res)
        return results

    async def get_entity(self, entity_id: uuid.UUID) -> GraphEntityRecord | None:
        """Retrieve an entity by ID."""
        if entity_id in self._entities:
            return self._entities[entity_id]

        if self._db is not None:
            db_ent = await self._db.get(DBGraphEntity, entity_id)
            if db_ent is not None:
                record = GraphEntityRecord(
                    entity_id=db_ent.id,
                    entity_type=EntityType(db_ent.entity_type),
                    name=db_ent.name,
                    canonical_name=db_ent.canonical_name,
                    project_id=db_ent.project_id,
                    source=db_ent.source,
                    confidence=db_ent.confidence,
                    metadata=db_ent.metadata_,
                    created_at=db_ent.created_at,
                    updated_at=db_ent.updated_at,
                )
                self._entities[record.entity_id] = record
                return record
        return None

    async def find_entities(
        self,
        name: str | None = None,
        entity_type: EntityType | str | None = None,
        project_id: uuid.UUID | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[GraphEntityRecord]:
        """
        Search entities by name, type, and project boundaries.
        """
        matches: list[GraphEntityRecord] = []
        query_norm = normalize_entity_name(name) if name else None
        target_type = EntityType(entity_type) if isinstance(entity_type, str) else entity_type

        for ent in self._entities.values():
            if ent.confidence < min_confidence:
                continue
            # Project isolation: matches project_id or global shared entities (project_id is None)
            if project_id is not None and ent.project_id is not None and ent.project_id != project_id:
                continue
            if target_type is not None and ent.entity_type != target_type:
                continue
            if query_norm:
                if query_norm != ent.canonical_name and query_norm not in ent.canonical_name:
                    continue

            matches.append(ent)
            if len(matches) >= limit:
                break

        return matches

    # ── Relationship Operations ───────────────────────────────────────────────

    async def upsert_relationship(self, relationship: GraphRelationshipRecord) -> GraphRelationshipRecord:
        """
        Insert or update a graph edge in memory and PostgreSQL.
        """
        relationship.updated_at = datetime.now(timezone.utc)
        self._relationships[relationship.relationship_id] = relationship

        # Update adjacency
        self._outgoing_adj.setdefault(relationship.source_entity_id, set()).add(relationship.relationship_id)
        self._incoming_adj.setdefault(relationship.target_entity_id, set()).add(relationship.relationship_id)

        if self._db is not None:
            try:
                db_rel = await self._db.get(DBGraphRelationship, relationship.relationship_id)
                if db_rel is None:
                    db_rel = DBGraphRelationship(
                        id=relationship.relationship_id,
                        source_entity_id=relationship.source_entity_id,
                        relationship_type=relationship.relationship_type.value,
                        target_entity_id=relationship.target_entity_id,
                        project_id=relationship.project_id,
                        confidence=relationship.confidence,
                        provenance=relationship.provenance,
                        is_inferred=relationship.is_inferred,
                    )
                    self._db.add(db_rel)
                else:
                    db_rel.relationship_type = relationship.relationship_type.value
                    db_rel.confidence = relationship.confidence
                    db_rel.provenance = relationship.provenance
                    db_rel.is_inferred = relationship.is_inferred
                    db_rel.updated_at = relationship.updated_at
                await self._db.flush()
            except Exception as exc:
                logger.warning("graph_store_db_rel_upsert_failed", error=str(exc))

        return relationship

    async def upsert_relationships(self, relationships: Sequence[GraphRelationshipRecord]) -> list[GraphRelationshipRecord]:
        """Batch upsert multiple relationships."""
        results: list[GraphRelationshipRecord] = []
        for rel in relationships:
            res = await self.upsert_relationship(rel)
            results.append(res)
        return results

    async def get_relationships_for_entity(
        self,
        entity_id: uuid.UUID,
        direction: str = "both",
        relationship_types: list[RelationshipType] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[GraphRelationshipRecord]:
        """
        Get all incoming, outgoing, or bidirectional relationships for a given node.
        """
        rel_ids: set[uuid.UUID] = set()
        if direction in ("out", "both"):
            rel_ids.update(self._outgoing_adj.get(entity_id, set()))
        if direction in ("in", "both"):
            rel_ids.update(self._incoming_adj.get(entity_id, set()))

        results: list[GraphRelationshipRecord] = []
        for rid in rel_ids:
            rel = self._relationships.get(rid)
            if rel is None:
                continue
            if project_id is not None and rel.project_id is not None and rel.project_id != project_id:
                continue
            if relationship_types and rel.relationship_type not in relationship_types:
                continue
            results.append(rel)

        return results

    # ── Traversal & Subgraphs ─────────────────────────────────────────────────

    async def get_subgraph(
        self,
        seed_entity_ids: Sequence[uuid.UUID],
        max_depth: int = 2,
        project_id: uuid.UUID | None = None,
        min_confidence: float = 0.0,
        include_inferred: bool = True,
    ) -> GraphSubGraph:
        """
        Extract bounded subgraph surrounding seed nodes using breadth-first traversal.
        """
        visited_nodes: set[uuid.UUID] = set()
        visited_rel_ids: set[uuid.UUID] = set()
        queue: deque[tuple[uuid.UUID, int]] = deque((sid, 0) for sid in seed_entity_ids if sid in self._entities)

        collected_entities: list[GraphEntityRecord] = []
        collected_relationships: list[GraphRelationshipRecord] = []

        while queue:
            curr_id, depth = queue.popleft()
            if curr_id in visited_nodes:
                continue
            visited_nodes.add(curr_id)

            curr_ent = self._entities.get(curr_id)
            if curr_ent is not None:
                if project_id is None or curr_ent.project_id is None or curr_ent.project_id == project_id:
                    collected_entities.append(curr_ent)

            if depth >= max_depth:
                continue

            # Traverse adjacent edges
            rels = await self.get_relationships_for_entity(curr_id, direction="both", project_id=project_id)
            for rel in rels:
                if rel.confidence < min_confidence:
                    continue
                if not include_inferred and rel.is_inferred:
                    continue

                if rel.relationship_id not in visited_rel_ids:
                    visited_rel_ids.add(rel.relationship_id)
                    collected_relationships.append(rel)

                neighbor_id = rel.target_entity_id if rel.source_entity_id == curr_id else rel.source_entity_id
                if neighbor_id not in visited_nodes:
                    queue.append((neighbor_id, depth + 1))

        return GraphSubGraph(entities=collected_entities, relationships=collected_relationships)

    async def find_paths(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        max_depth: int = 3,
        project_id: uuid.UUID | None = None,
    ) -> list[GraphPath]:
        """
        Find connecting paths between source and target entities up to max_depth.
        """
        if source_id not in self._entities or target_id not in self._entities:
            return []

        paths: list[GraphPath] = []
        # Queue contains: (current_node_id, [visited_node_ids], [visited_rel_records])
        queue: deque[tuple[uuid.UUID, list[uuid.UUID], list[GraphRelationshipRecord]]] = deque()
        queue.append((source_id, [source_id], []))

        while queue:
            curr_id, node_path, rel_path = queue.popleft()

            if curr_id == target_id and len(node_path) > 1:
                ent_records = [self._entities[nid] for nid in node_path if nid in self._entities]
                path_conf = 1.0
                for r in rel_path:
                    path_conf *= r.confidence
                paths.append(GraphPath(entities=ent_records, relationships=rel_path, confidence=round(path_conf, 3)))
                continue

            if len(node_path) > max_depth:
                continue

            # Get outgoing and incoming neighbors
            rels = await self.get_relationships_for_entity(curr_id, direction="both", project_id=project_id)
            for rel in rels:
                neighbor_id = rel.target_entity_id if rel.source_entity_id == curr_id else rel.source_entity_id
                if neighbor_id not in node_path:
                    queue.append((neighbor_id, node_path + [neighbor_id], rel_path + [rel]))

        return paths

    # ── Invalidation & Stale Entity Cleanup ───────────────────────────────────

    async def cleanup_source_graph(self, source_prefix: str, project_id: uuid.UUID | None = None) -> int:
        """
        Delete entities originating from a specific source (e.g. 'file:path') and prune stale edges.
        """
        entities_to_delete: list[uuid.UUID] = []
        for eid, ent in list(self._entities.items()):
            if ent.source.startswith(source_prefix):
                if project_id is None or ent.project_id == project_id:
                    entities_to_delete.append(eid)

        if not entities_to_delete:
            return 0

        # Remove entities and connected relationships from memory
        deleted_count = len(entities_to_delete)
        for eid in entities_to_delete:
            # Delete outgoing & incoming edges
            out_rels = self._outgoing_adj.pop(eid, set())
            in_rels = self._incoming_adj.pop(eid, set())
            all_rels = out_rels | in_rels

            for rid in all_rels:
                if rid in self._relationships:
                    rel = self._relationships.pop(rid)
                    # Also prune from corresponding other side's adj set
                    if rel.source_entity_id in self._outgoing_adj:
                        self._outgoing_adj[rel.source_entity_id].discard(rid)
                    if rel.target_entity_id in self._incoming_adj:
                        self._incoming_adj[rel.target_entity_id].discard(rid)

            self._entities.pop(eid, None)

        # Delete from DB if connected
        if self._db is not None:
            try:
                stmt_rels = delete(DBGraphRelationship).where(
                    (DBGraphRelationship.source_entity_id.in_(entities_to_delete))
                    | (DBGraphRelationship.target_entity_id.in_(entities_to_delete))
                )
                await self._db.execute(stmt_rels)

                stmt_ents = delete(DBGraphEntity).where(DBGraphEntity.id.in_(entities_to_delete))
                await self._db.execute(stmt_ents)
                await self._db.flush()
            except Exception as exc:
                logger.warning("graph_store_db_cleanup_failed", error=str(exc))

        logger.info("graph_source_cleaned", source_prefix=source_prefix, deleted_entities=deleted_count)
        return deleted_count

    def clear(self) -> None:
        """Clear all in-memory graph state."""
        self._entities.clear()
        self._relationships.clear()
        self._outgoing_adj.clear()
        self._incoming_adj.clear()
