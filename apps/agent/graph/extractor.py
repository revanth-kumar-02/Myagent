"""
graph.extractor — Entity and Relationship Extraction Subsystem (V11).

Extracts typed entities and structural relationships from:
  - Source code files & AST/regex parsed symbols
  - Documents (Markdown, PDF, DOCX, XLSX, PPTX, CSV)
  - Long-term Memories (RAG V5)
  - Web Research search results & fetched pages (V6 DuckDuckGo)
  - Autonomous Tasks & Automation plans (V9)
  - User search queries (seed discovery)
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

import structlog

from graph.types import (
    EntityType,
    GraphEntityRecord,
    GraphRelationshipRecord,
    RelationshipType,
    normalize_entity_name,
)

logger = structlog.get_logger(__name__)

# Known popular tech/libraries for robust discovery
KNOWN_TECHNOLOGIES = {
    "python", "typescript", "javascript", "postgresql", "postgres", "sqlite",
    "pgvector", "redis", "fastapi", "sqlalchemy", "alembic", "pydantic",
    "docker", "pytest", "structlog", "apscheduler", "duckduckgo", "tiktoken",
    "beautifulsoup", "bs4", "react", "nextjs", "vue", "flutter", "dart",
    "qwen", "gemma", "huggingface", "transformers", "pytorch", "torch", "pandas",
    "numpy", "openai", "gemini", "anthropic", "vllm", "ollama", "git", "linux"
}

_CODE_CLASS_PATTERN = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\(([^)]+)\))?\s*:", re.MULTILINE)
_CODE_FUNC_PATTERN = re.compile(r"^\s*(?:async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_CODE_IMPORT_PATTERN = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))", re.MULTILINE)
_HEADING_PATTERN = re.compile(r"^(?:#{1,6}|\d+\.)\s+(.+)$", re.MULTILINE)


class EntityExtractor:
    """
    Extracts high-fidelity entities and relationships across heterogeneous inputs.
    """

    def extract_from_code(
        self,
        content: str,
        file_path: str,
        project_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[list[GraphEntityRecord], list[GraphRelationshipRecord]]:
        """
        Extract File, CodeSymbol, Technology entities and containment/dependency relationships.
        """
        entities: list[GraphEntityRecord] = []
        relationships: list[GraphRelationshipRecord] = []
        source_tag = f"file:{file_path}"
        meta = metadata or {}

        # 1. File Entity
        file_name = os.path.basename(file_path)
        file_entity = GraphEntityRecord(
            name=file_name,
            entity_type=EntityType.FILE,
            source=source_tag,
            project_id=project_id,
            confidence=1.0,
            metadata={"file_path": file_path, "language": meta.get("language", "python")},
        )
        entities.append(file_entity)

        # 2. Extract Classes and Inheritance
        seen_symbols: set[str] = set()
        for match in _CODE_CLASS_PATTERN.finditer(content):
            cls_name = match.group(1)
            bases_raw = match.group(2)
            if cls_name in seen_symbols:
                continue
            seen_symbols.add(cls_name)

            cls_entity = GraphEntityRecord(
                name=cls_name,
                entity_type=EntityType.CODE_SYMBOL,
                source=source_tag,
                project_id=project_id,
                confidence=1.0,
                metadata={"file_path": file_path, "kind": "class"},
            )
            entities.append(cls_entity)

            # File CONTAINS Class
            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=file_entity.entity_id,
                    relationship_type=RelationshipType.CONTAINS,
                    target_entity_id=cls_entity.entity_id,
                    project_id=project_id,
                    confidence=1.0,
                    provenance={"source_type": "code_ast", "file_path": file_path},
                    is_inferred=False,
                )
            )
            # Class BELONGS_TO File
            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=cls_entity.entity_id,
                    relationship_type=RelationshipType.BELONGS_TO,
                    target_entity_id=file_entity.entity_id,
                    project_id=project_id,
                    confidence=1.0,
                    provenance={"source_type": "code_ast", "file_path": file_path},
                    is_inferred=False,
                )
            )

            # Check inheritance / base classes
            if bases_raw:
                for base in [b.strip() for b in bases_raw.split(",") if b.strip()]:
                    if base not in ("object", "Base", "BaseModel"):
                        base_entity = GraphEntityRecord(
                            name=base,
                            entity_type=EntityType.CODE_SYMBOL,
                            source=source_tag,
                            project_id=project_id,
                            confidence=0.85,
                            metadata={"is_reference": True},
                        )
                        entities.append(base_entity)
                        # Class IMPLEMENTS/REFERENCES Base
                        relationships.append(
                            GraphRelationshipRecord(
                                source_entity_id=cls_entity.entity_id,
                                relationship_type=RelationshipType.IMPLEMENTS,
                                target_entity_id=base_entity.entity_id,
                                project_id=project_id,
                                confidence=0.9,
                                provenance={"source_type": "inheritance", "file_path": file_path},
                                is_inferred=False,
                            )
                        )

        # 3. Extract Functions and Methods
        for match in _CODE_FUNC_PATTERN.finditer(content):
            fn_name = match.group(1)
            if fn_name.startswith("__") and fn_name.endswith("__"):
                continue  # skip dunder boilerplate
            if fn_name in seen_symbols:
                continue
            seen_symbols.add(fn_name)

            fn_entity = GraphEntityRecord(
                name=fn_name,
                entity_type=EntityType.CODE_SYMBOL,
                source=source_tag,
                project_id=project_id,
                confidence=1.0,
                metadata={"file_path": file_path, "kind": "function"},
            )
            entities.append(fn_entity)

            # File CONTAINS Function
            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=file_entity.entity_id,
                    relationship_type=RelationshipType.CONTAINS,
                    target_entity_id=fn_entity.entity_id,
                    project_id=project_id,
                    confidence=1.0,
                    provenance={"source_type": "code_ast", "file_path": file_path},
                    is_inferred=False,
                )
            )

        # 4. Extract Imports / Technologies
        seen_imports: set[str] = set()
        for match in _CODE_IMPORT_PATTERN.finditer(content):
            raw_pkg = match.group(1) or match.group(2)
            if not raw_pkg:
                continue
            top_level = raw_pkg.split(".")[0].lower()
            if top_level in seen_imports or top_level in ("os", "sys", "re", "json", "typing", "datetime", "uuid", "math", "time"):
                continue
            seen_imports.add(top_level)

            tech_entity = GraphEntityRecord(
                name=top_level,
                entity_type=EntityType.TECHNOLOGY,
                source=source_tag,
                project_id=project_id,
                confidence=0.95,
                metadata={"import_name": top_level},
            )
            entities.append(tech_entity)

            # File DEPENDS_ON / USES Technology
            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=file_entity.entity_id,
                    relationship_type=RelationshipType.USES,
                    target_entity_id=tech_entity.entity_id,
                    project_id=project_id,
                    confidence=0.95,
                    provenance={"source_type": "import_statement", "file_path": file_path},
                    is_inferred=False,
                )
            )

        return entities, relationships

    def extract_from_document(
        self,
        content: str,
        file_path: str,
        project_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[list[GraphEntityRecord], list[GraphRelationshipRecord]]:
        """
        Extract Document, Concept/Heading, Technology entities and hierarchical containment.
        """
        entities: list[GraphEntityRecord] = []
        relationships: list[GraphRelationshipRecord] = []
        source_tag = f"file:{file_path}"
        meta = metadata or {}

        # 1. Document Entity
        doc_name = os.path.basename(file_path)
        doc_entity = GraphEntityRecord(
            name=doc_name,
            entity_type=EntityType.DOCUMENT,
            source=source_tag,
            project_id=project_id,
            confidence=1.0,
            metadata={"file_path": file_path, "type": meta.get("type", "document")},
        )
        entities.append(doc_entity)

        # 2. Extract Headings / Concepts
        for match in _HEADING_PATTERN.finditer(content):
            heading = match.group(1).strip()
            # Clean Markdown formatting
            heading_clean = re.sub(r"[`*_#]", "", heading).strip()
            if len(heading_clean) < 3 or len(heading_clean) > 80:
                continue

            concept_entity = GraphEntityRecord(
                name=heading_clean,
                entity_type=EntityType.CONCEPT,
                source=source_tag,
                project_id=project_id,
                confidence=0.9,
                metadata={"file_path": file_path, "heading": heading_clean},
            )
            entities.append(concept_entity)

            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=doc_entity.entity_id,
                    relationship_type=RelationshipType.CONTAINS,
                    target_entity_id=concept_entity.entity_id,
                    project_id=project_id,
                    confidence=0.9,
                    provenance={"source_type": "document_heading", "file_path": file_path},
                    is_inferred=False,
                )
            )

        # 3. Discover mentioned Technologies in Document
        lower_content = content.lower()
        for tech in KNOWN_TECHNOLOGIES:
            if re.search(rf"\b{re.escape(tech)}\b", lower_content):
                tech_entity = GraphEntityRecord(
                    name=tech,
                    entity_type=EntityType.TECHNOLOGY,
                    source=source_tag,
                    project_id=project_id,
                    confidence=0.85,
                )
                entities.append(tech_entity)

                relationships.append(
                    GraphRelationshipRecord(
                        source_entity_id=doc_entity.entity_id,
                        relationship_type=RelationshipType.REFERENCES,
                        target_entity_id=tech_entity.entity_id,
                        project_id=project_id,
                        confidence=0.85,
                        provenance={"source_type": "document_mention", "file_path": file_path},
                        is_inferred=False,
                    )
                )

        return entities, relationships

    def extract_from_memory(
        self,
        memory_content: str,
        memory_type: str,
        memory_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
        source: str = "user_explicit",
    ) -> tuple[list[GraphEntityRecord], list[GraphRelationshipRecord]]:
        """
        Extract Person (User), Technology, and Concept entities linked to persistent memories.
        """
        entities: list[GraphEntityRecord] = []
        relationships: list[GraphRelationshipRecord] = []
        source_tag = f"memory:{memory_id}"

        # 1. User/Person Entity
        user_entity = GraphEntityRecord(
            name="User",
            entity_type=EntityType.PERSON,
            source=source_tag,
            project_id=project_id,
            confidence=1.0,
            metadata={"role": "user"},
        )
        entities.append(user_entity)

        # 2. Extract technologies mentioned in memory
        lower_content = memory_content.lower()
        for tech in KNOWN_TECHNOLOGIES:
            if re.search(rf"\b{re.escape(tech)}\b", lower_content):
                tech_entity = GraphEntityRecord(
                    name=tech,
                    entity_type=EntityType.TECHNOLOGY,
                    source=source_tag,
                    project_id=project_id,
                    confidence=0.9,
                )
                entities.append(tech_entity)

                rel_type = RelationshipType.USES if "use" in lower_content or "prefer" in lower_content else RelationshipType.RELATED_TO
                relationships.append(
                    GraphRelationshipRecord(
                        source_entity_id=user_entity.entity_id,
                        relationship_type=rel_type,
                        target_entity_id=tech_entity.entity_id,
                        project_id=project_id,
                        confidence=0.9,
                        provenance={"source_type": "user_memory", "memory_id": str(memory_id), "memory_type": memory_type},
                        is_inferred=False,
                    )
                )

        # 3. Create Concept entity from memory content title/summary
        clean_text = memory_content.strip()
        if len(clean_text) > 5:
            concept_name = clean_text[:60] + "..." if len(clean_text) > 60 else clean_text
            concept_entity = GraphEntityRecord(
                name=concept_name,
                entity_type=EntityType.CONCEPT,
                source=source_tag,
                project_id=project_id,
                confidence=0.85,
                metadata={"memory_type": memory_type, "full_content": memory_content},
            )
            entities.append(concept_entity)

            relationships.append(
                GraphRelationshipRecord(
                    source_entity_id=user_entity.entity_id,
                    relationship_type=RelationshipType.CREATED_BY if source == "user_explicit" else RelationshipType.RELATED_TO,
                    target_entity_id=concept_entity.entity_id,
                    project_id=project_id,
                    confidence=0.85,
                    provenance={"source_type": "user_memory", "memory_id": str(memory_id)},
                    is_inferred=False,
                )
            )

        return entities, relationships

    def extract_from_web_source(
        self,
        url: str,
        title: str,
        snippet: str,
        domain: str = "",
        project_id: uuid.UUID | None = None,
    ) -> tuple[list[GraphEntityRecord], list[GraphRelationshipRecord]]:
        """
        Extract WebSource and referenced Technologies/Concepts from web search results.
        """
        entities: list[GraphEntityRecord] = []
        relationships: list[GraphRelationshipRecord] = []
        source_tag = f"web:{url}"

        # 1. Web Source Entity
        web_entity = GraphEntityRecord(
            name=title or domain or url,
            entity_type=EntityType.WEB_SOURCE,
            source=source_tag,
            project_id=project_id,
            confidence=0.9,
            metadata={"url": url, "domain": domain, "snippet": snippet[:200]},
        )
        entities.append(web_entity)

        # 2. Extract Technologies & Concepts
        combined_text = (title + " " + snippet).lower()
        for tech in KNOWN_TECHNOLOGIES:
            if re.search(rf"\b{re.escape(tech)}\b", combined_text):
                tech_entity = GraphEntityRecord(
                    name=tech,
                    entity_type=EntityType.TECHNOLOGY,
                    source=source_tag,
                    project_id=project_id,
                    confidence=0.8,
                )
                entities.append(tech_entity)

                relationships.append(
                    GraphRelationshipRecord(
                        source_entity_id=web_entity.entity_id,
                        relationship_type=RelationshipType.REFERENCES,
                        target_entity_id=tech_entity.entity_id,
                        project_id=project_id,
                        confidence=0.8,
                        provenance={"source_type": "web_research", "url": url},
                        is_inferred=False,
                    )
                )

        return entities, relationships

    def extract_from_task(
        self,
        task_id: uuid.UUID,
        goal: str,
        tool_names: list[str] | None = None,
        dependencies: list[Any] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> tuple[list[GraphEntityRecord], list[GraphRelationshipRecord]]:
        """
        Extract Task and related Tool/Dependency entities.
        """
        entities: list[GraphEntityRecord] = []
        relationships: list[GraphRelationshipRecord] = []
        source_tag = f"task:{task_id}"

        # 1. Task Entity
        task_entity = GraphEntityRecord(
            name=goal[:80],
            entity_type=EntityType.TASK,
            source=source_tag,
            project_id=project_id,
            confidence=1.0,
            metadata={"goal": goal, "task_id": str(task_id)},
        )
        entities.append(task_entity)

        # 2. Tool Entities
        if tool_names:
            for tool_name in tool_names:
                tool_entity = GraphEntityRecord(
                    name=tool_name,
                    entity_type=EntityType.TECHNOLOGY,
                    source=source_tag,
                    project_id=project_id,
                    confidence=0.95,
                    metadata={"kind": "tool"},
                )
                entities.append(tool_entity)

                relationships.append(
                    GraphRelationshipRecord(
                        source_entity_id=task_entity.entity_id,
                        relationship_type=RelationshipType.USES,
                        target_entity_id=tool_entity.entity_id,
                        project_id=project_id,
                        confidence=0.95,
                        provenance={"source_type": "task_plan", "task_id": str(task_id)},
                        is_inferred=False,
                    )
                )

        return entities, relationships

    def extract_from_query(self, query: str) -> list[str]:
        """
        Extract candidate entity names / symbols / keywords mentioned in a user prompt.
        """
        candidates: list[str] = []
        cleaned = query.strip()
        if not cleaned:
            return candidates

        # 1. Look for known technologies
        lower_q = cleaned.lower()
        for tech in KNOWN_TECHNOLOGIES:
            if re.search(rf"\b{re.escape(tech)}\b", lower_q):
                candidates.append(tech)

        # 2. Look for PascalCase (classes) or snake_case (functions/files)
        pascal_cases = re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}\b", cleaned)
        candidates.extend(pascal_cases)

        snake_cases = re.findall(r"\b[a-z_][a-z0-9_]{3,}\b", cleaned)
        for sc in snake_cases:
            if sc not in ("what", "where", "show", "find", "code", "file", "project", "with", "from", "that", "this"):
                candidates.append(sc)

        # 3. Look for file extensions or paths
        file_matches = re.findall(r"[A-Za-z0-9_\-./]+\.[a-z]{2,4}", cleaned)
        candidates.extend(file_matches)

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for c in candidates:
            norm = normalize_entity_name(c)
            if norm not in seen and len(norm) >= 2:
                seen.add(norm)
                deduped.append(c)

        return deduped
