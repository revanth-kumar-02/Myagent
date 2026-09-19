"""
graph.builder — Relationship Builder & Cross-Source Inference Subsystem (V11).

Builds explicit and inferred connections across:
  - Code symbols and documentation headings
  - User memory preferences and codebase technologies
  - Tasks, tools, and referenced modules
  - Web research findings and project concepts
  - Contradiction detection between conflicting specs/memories

Strictly maintains provenance and flags all inferred links (`is_inferred=True`).
"""

from __future__ import annotations

import re
import uuid
from typing import Sequence

import structlog

from graph.types import (
    EntityType,
    GraphEntityRecord,
    GraphRelationshipRecord,
    RelationshipType,
    normalize_entity_name,
)

logger = structlog.get_logger(__name__)


class RelationshipBuilder:
    """
    Constructs cross-source graph relationships and derives semantic inferences with strict provenance.
    """

    def build_cross_source_links(
        self,
        entities: Sequence[GraphEntityRecord],
        existing_relationships: Sequence[GraphRelationshipRecord] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[GraphRelationshipRecord]:
        """
        Connects entities across different sources (Code, Memory, Web, Docs, Tasks).
        """
        new_relationships: list[GraphRelationshipRecord] = []
        entity_by_canonical: dict[str, list[GraphEntityRecord]] = {}

        for e in entities:
            # Respect project isolation: match within same project or shared global entities
            if project_id is not None and e.project_id is not None and e.project_id != project_id:
                continue
            entity_by_canonical.setdefault(e.canonical_name, []).append(e)

        # 1. Exact Name Matching across different entity types (e.g., Tech "pgvector" & Memory mentioning "pgvector")
        for name, group in entity_by_canonical.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    e1, e2 = group[i], group[j]
                    if e1.entity_id == e2.entity_id or e1.source == e2.source:
                        continue

                    rel_type = self._determine_relationship_type(e1, e2)
                    rel = GraphRelationshipRecord(
                        source_entity_id=e1.entity_id,
                        relationship_type=rel_type,
                        target_entity_id=e2.entity_id,
                        project_id=project_id or e1.project_id or e2.project_id,
                        confidence=min(e1.confidence, e2.confidence) * 0.95,
                        provenance={
                            "source_type": "cross_source_exact_match",
                            "evidence": f"Entities '{e1.name}' ({e1.entity_type.value}) and '{e2.name}' ({e2.entity_type.value}) share canonical name '{name}'",
                            "e1_source": e1.source,
                            "e2_source": e2.source,
                        },
                        is_inferred=False,
                    )
                    new_relationships.append(rel)

        return new_relationships

    def infer_semantic_links(
        self,
        entities: Sequence[GraphEntityRecord],
        relationships: Sequence[GraphRelationshipRecord],
        project_id: uuid.UUID | None = None,
    ) -> list[GraphRelationshipRecord]:
        """
        Infers second-degree links across graph paths with explicit inferred marking.
        """
        inferred_links: list[GraphRelationshipRecord] = []
        entity_map = {e.entity_id: e for e in entities}

        # Build adjacency for traversal
        adj: dict[uuid.UUID, list[GraphRelationshipRecord]] = {}
        for r in relationships:
            adj.setdefault(r.source_entity_id, []).append(r)

        # 1. Transitive containment: If File A CONTAINS Symbol B, and Symbol B USES Tech C -> File A USES Tech C (inferred)
        for r1 in relationships:
            if r1.relationship_type == RelationshipType.CONTAINS:
                target_sym_id = r1.target_entity_id
                for r2 in adj.get(target_sym_id, []):
                    if r2.relationship_type in (RelationshipType.USES, RelationshipType.DEPENDS_ON):
                        file_id = r1.source_entity_id
                        tech_id = r2.target_entity_id

                        file_ent = entity_map.get(file_id)
                        tech_ent = entity_map.get(tech_id)
                        if file_ent and tech_ent:
                            inferred_rel = GraphRelationshipRecord(
                                source_entity_id=file_id,
                                relationship_type=RelationshipType.USES,
                                target_entity_id=tech_id,
                                project_id=project_id,
                                confidence=round(r1.confidence * r2.confidence * 0.85, 2),
                                provenance={
                                    "source_type": "transitive_inference",
                                    "evidence": f"File '{file_ent.name}' contains '{entity_map[target_sym_id].name}' which uses '{tech_ent.name}'",
                                    "intermediate_entity_id": str(target_sym_id),
                                },
                                is_inferred=True,  # ALWAYS flagged as inferred
                            )
                            inferred_links.append(inferred_rel)

        return inferred_links

    def detect_contradictions(
        self,
        entities: Sequence[GraphEntityRecord],
        project_id: uuid.UUID | None = None,
    ) -> list[GraphRelationshipRecord]:
        """
        Detects conflicting preferences or contradictory technologies/rules.
        """
        contradictions: list[GraphRelationshipRecord] = []
        # Check for opposing directives in memories / concepts
        # e.g., "use postgresql" vs "use mysql" or "sqlite only"
        tech_entities = [e for e in entities if e.entity_type == EntityType.TECHNOLOGY]
        doc_concepts = [e for e in entities if e.entity_type in (EntityType.CONCEPT, EntityType.DOCUMENT)]

        for concept in doc_concepts:
            text = str(concept.metadata.get("full_content", concept.name)).lower()
            if any(neg in text for neg in ("no ", "never", "do not use", "avoid", "deprecated", "forbid")):
                for tech in tech_entities:
                    neg_pattern = rf"\b(?:no|never|do not use|avoid|deprecated|forbid)(?:\s+use|\s+using)?\s+{re.escape(tech.canonical_name)}\b"
                    if re.search(neg_pattern, text):
                        rel = GraphRelationshipRecord(
                            source_entity_id=concept.entity_id,
                            relationship_type=RelationshipType.CONTRADICTS,
                            target_entity_id=tech.entity_id,
                            project_id=project_id or concept.project_id,
                            confidence=0.9,
                            provenance={
                                "source_type": "contradiction_detection",
                                "evidence": f"Rule/Concept '{concept.name}' explicitly forbids or contradicts usage of '{tech.name}'",
                                "concept_source": concept.source,
                            },
                            is_inferred=False,
                        )
                        contradictions.append(rel)

        return contradictions

    def _determine_relationship_type(self, e1: GraphEntityRecord, e2: GraphEntityRecord) -> RelationshipType:
        """Helper to decide semantic relationship based on entity type pair."""
        t1, t2 = e1.entity_type, e2.entity_type
        if t1 == EntityType.FILE and t2 == EntityType.CODE_SYMBOL:
            return RelationshipType.CONTAINS
        if t1 == EntityType.CODE_SYMBOL and t2 == EntityType.FILE:
            return RelationshipType.BELONGS_TO
        if t1 == EntityType.TASK and t2 == EntityType.TECHNOLOGY:
            return RelationshipType.USES
        if t1 in (EntityType.FILE, EntityType.CODE_SYMBOL) and t2 == EntityType.TECHNOLOGY:
            return RelationshipType.USES
        if t1 == EntityType.WEB_SOURCE:
            return RelationshipType.REFERENCES
        if t1 == EntityType.PERSON:
            return RelationshipType.RELATED_TO
        return RelationshipType.RELATED_TO
