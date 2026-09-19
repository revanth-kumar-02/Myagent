"""
graph.types — Data models and types for Kora Knowledge Graph (V11).

Defines all entity types, relationship types, record containers, and query structures.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class EntityType(str, enum.Enum):
    """Supported entity categories in the Kora Knowledge Graph."""
    PERSON       = "person"        # User, author, developer, team member
    PROJECT      = "project"       # Codebase, repository, software project
    ORGANIZATION = "organization"  # Company, open-source org, vendor
    FILE         = "file"          # Source code file, asset, config file
    DOCUMENT     = "document"      # Structured or unstructured document (PDF, docx, etc.)
    CODE_SYMBOL  = "code_symbol"   # Class, function, method, interface, struct
    TASK         = "task"          # Autonomous plan task, goal, workflow job
    TECHNOLOGY   = "technology"    # Framework, language, database, library, tool
    CONCEPT      = "concept"       # Domain concept, pattern, architecture topic
    WEB_SOURCE   = "web_source"    # Domain, URL, web article, external page


class RelationshipType(str, enum.Enum):
    """Supported semantic and structural relationship types."""
    BELONGS_TO   = "belongs_to"    # Symbol belongs to File, File belongs to Project
    REFERENCES   = "references"    # File/Code/Doc references another entity
    DEPENDS_ON   = "depends_on"    # Component/Task depends on library/file/task
    CREATED_BY   = "created_by"    # Document/Memory/Code created by Person
    RELATED_TO   = "related_to"    # General semantic association
    CONTAINS     = "contains"      # File contains Symbol, Project contains File
    IMPLEMENTS   = "implements"    # Class implements Interface/Protocol
    USES         = "uses"          # Component/Code/Task uses Tool/Technology
    DERIVED_FROM = "derived_from"  # Evidence/Result derived from WebSource/Doc
    CONTRADICTS  = "contradicts"   # Conflicting facts/memories/preferences


def normalize_entity_name(name: str) -> str:
    """Normalize entity names for canonical lookups and matching."""
    return name.strip().lower()


@dataclass
class GraphEntityRecord:
    """Represents a node in the Kora Knowledge Graph."""
    name: str
    entity_type: EntityType
    source: str                          # e.g. 'file:path', 'chunk:id', 'memory:id', 'web:url', 'task:id'
    entity_id: uuid.UUID = field(default_factory=uuid.uuid4)
    canonical_name: str = ""
    project_id: uuid.UUID | None = None  # None = shared/global entity
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.canonical_name:
            self.canonical_name = normalize_entity_name(self.name)
        if isinstance(self.entity_type, str):
            self.entity_type = EntityType(self.entity_type)


@dataclass
class GraphRelationshipRecord:
    """Represents a directed edge between two nodes in the Knowledge Graph."""
    source_entity_id: uuid.UUID
    relationship_type: RelationshipType
    target_entity_id: uuid.UUID
    relationship_id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID | None = None
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    is_inferred: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.relationship_type, str):
            self.relationship_type = RelationshipType(self.relationship_type)


@dataclass
class GraphPath:
    """Represents a path traversal between two entities."""
    entities: list[GraphEntityRecord] = field(default_factory=list)
    relationships: list[GraphRelationshipRecord] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class GraphSubGraph:
    """A bounded subgraph of entities and their connecting relationships."""
    entities: list[GraphEntityRecord] = field(default_factory=list)
    relationships: list[GraphRelationshipRecord] = field(default_factory=list)

    @property
    def entity_map(self) -> dict[uuid.UUID, GraphEntityRecord]:
        return {e.entity_id: e for e in self.entities}


@dataclass
class GraphQuery:
    """Search / traversal query for Knowledge Graph retrieval."""
    query_text: str = ""
    entity_names: list[str] = field(default_factory=list)
    entity_types: list[EntityType] | None = None
    relationship_types: list[RelationshipType] | None = None
    project_id: uuid.UUID | None = None
    max_depth: int = 2
    min_confidence: float = 0.5
    include_inferred: bool = True
    limit_entities: int = 20


@dataclass
class GraphQueryResult:
    """Results from querying the Knowledge Graph."""
    seed_entities: list[GraphEntityRecord] = field(default_factory=list)
    subgraph: GraphSubGraph = field(default_factory=GraphSubGraph)
    paths: list[GraphPath] = field(default_factory=list)
    total_entities: int = 0
    total_relationships: int = 0


@dataclass
class FormattedGraphContext:
    """Context block formatted for LLM consumption with token metrics."""
    text: str
    token_count: int
    verified_relationships_count: int
    inferred_relationships_count: int
    entities_count: int
