"""
graph.retriever — Graph-Assisted Retrieval & Cross-Source Context Subsystem (V11).

Responsibilities:
  - Identify seed entities from incoming user queries
  - Traverse local subgraphs to discover connected components, dependencies, and rules
  - Extract structured GraphEvidence objects for AgentContextPackage
  - Format bounded Markdown context for LLM grounding with strict separation of verified vs inferred links
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
import tiktoken

from core.types import GraphEvidence
from graph.extractor import EntityExtractor
from graph.store import GraphStore
from graph.types import (
    FormattedGraphContext,
    GraphEntityRecord,
    GraphQuery,
    GraphQueryResult,
    GraphRelationshipRecord,
    RelationshipType,
)

logger = structlog.get_logger(__name__)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class GraphRetriever:
    """
    Retrieves and formats Knowledge Graph context to augment RAG, Memory, and Reasoning.
    """

    def __init__(self, store: GraphStore, extractor: EntityExtractor | None = None) -> None:
        self.store = store
        self.extractor = extractor or EntityExtractor()

    async def query_subgraph(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_depth: int = 2,
        min_confidence: float = 0.5,
        limit_seeds: int = 10,
    ) -> GraphQueryResult:
        """
        Extract seed entities for query and expand their subgraph up to max_depth.
        """
        # 1. Discover candidate entity keywords from query
        candidate_terms = self.extractor.extract_from_query(query)
        seed_entities: list[GraphEntityRecord] = []
        seen_ids: set[uuid.UUID] = set()

        for term in candidate_terms[:limit_seeds]:
            matches = await self.store.find_entities(
                name=term,
                project_id=project_id,
                min_confidence=min_confidence,
                limit=3,
            )
            for m in matches:
                if m.entity_id not in seen_ids:
                    seen_ids.add(m.entity_id)
                    seed_entities.append(m)

        if not seed_entities:
            return GraphQueryResult()

        # 2. Extract subgraph
        subgraph = await self.store.get_subgraph(
            seed_entity_ids=[e.entity_id for e in seed_entities],
            max_depth=max_depth,
            project_id=project_id,
            min_confidence=min_confidence,
            include_inferred=True,
        )

        return GraphQueryResult(
            seed_entities=seed_entities,
            subgraph=subgraph,
            total_entities=len(subgraph.entities),
            total_relationships=len(subgraph.relationships),
        )

    async def get_graph_evidence(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_depth: int = 2,
    ) -> list[GraphEvidence]:
        """
        Returns structured GraphEvidence records for inclusion into AgentContextPackage.
        """
        query_res = await self.query_subgraph(query, project_id=project_id, max_depth=max_depth)
        subgraph = query_res.subgraph
        ent_map = subgraph.entity_map
        evidence_list: list[GraphEvidence] = []

        for rel in subgraph.relationships:
            src_ent = ent_map.get(rel.source_entity_id)
            tgt_ent = ent_map.get(rel.target_entity_id)
            if not src_ent or not tgt_ent:
                continue

            evidence_text = rel.provenance.get("evidence", f"{src_ent.name} {rel.relationship_type.value} {tgt_ent.name}")
            source_prov = rel.provenance.get("source_type", src_ent.source)

            item = GraphEvidence(
                source_entity=src_ent.name,
                relationship_type=rel.relationship_type.value,
                target_entity=tgt_ent.name,
                confidence=rel.confidence,
                provenance_source=source_prov,
                is_inferred=rel.is_inferred,
                evidence_text=evidence_text,
            )
            evidence_list.append(item)

        return evidence_list

    async def retrieve_formatted_context(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        max_depth: int = 2,
        max_tokens: int = 1024,
    ) -> FormattedGraphContext:
        """
        Assemble bounded Markdown section distinguishing verified facts from inferred relations.
        """
        query_res = await self.query_subgraph(query, project_id=project_id, max_depth=max_depth)
        subgraph = query_res.subgraph
        if not subgraph.entities:
            return FormattedGraphContext(
                text="",
                token_count=0,
                verified_relationships_count=0,
                inferred_relationships_count=0,
                entities_count=0,
            )

        ent_map = subgraph.entity_map
        verified_lines: list[str] = []
        inferred_lines: list[str] = []

        for rel in subgraph.relationships:
            src = ent_map.get(rel.source_entity_id)
            tgt = ent_map.get(rel.target_entity_id)
            if not src or not tgt:
                continue

            # Format representation
            rel_str = rel.relationship_type.value.upper()
            line = f"• [{src.entity_type.value.upper()}] {src.name} —[{rel_str}]→ [{tgt.entity_type.value.upper()}] {tgt.name} (confidence: {rel.confidence:.2f})"
            if rel.provenance.get("evidence"):
                line += f" | {rel.provenance['evidence']}"

            if rel.is_inferred:
                inferred_lines.append(line)
            else:
                verified_lines.append(line)

        # Build formatted text within token limits
        sections: list[str] = []
        if verified_lines:
            sections.append("Verified Relationships (Source-backed Facts):\n" + "\n".join(verified_lines))
        if inferred_lines:
            sections.append("Inferred / Associated Links (Potential Context):\n" + "\n".join(inferred_lines))

        raw_text = "\n\n".join(sections)
        token_count = len(_TOKENIZER.encode(raw_text))

        # Truncate lines if budget is exceeded
        if token_count > max_tokens:
            truncated_lines = verified_lines[:8] + (inferred_lines[:4] if inferred_lines else [])
            raw_text = "Verified & Inferred Graph Relationships:\n" + "\n".join(truncated_lines)
            token_count = len(_TOKENIZER.encode(raw_text))

        return FormattedGraphContext(
            text=raw_text,
            token_count=token_count,
            verified_relationships_count=len(verified_lines),
            inferred_relationships_count=len(inferred_lines),
            entities_count=len(subgraph.entities),
        )
