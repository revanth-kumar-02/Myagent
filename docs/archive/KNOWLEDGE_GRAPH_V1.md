# Kora — V11: Knowledge Graph & Cross-Source Intelligence

## 1. Overview & Purpose
The **Kora Knowledge Graph (V11)** connects heterogeneous information across:
- **Projects & Codebases**: Source files, AST classes, functions, interfaces, structs, imports.
- **Documents**: Markdown, PDF, DOCX, XLSX, PPTX, CSV headings, sections, concepts.
- **Long-Term Memories (RAG V5)**: User preferences, background profile, past decisions, workflow patterns.
- **Web Research (V6 DuckDuckGo)**: Web sources, domains, article topics, external documentation.
- **Autonomous Tasks & Automations (V9)**: Goals, tool usage, step dependencies, execution state.

The Knowledge Graph enables cross-source reasoning, architecture discovery, dependency graph resolution, and entity-guided RAG retrieval without introducing external graph databases.

---

## 2. Architecture & Data Flow

```
+-----------------------------------------------------------------------+
|                       Heterogeneous Sources                           |
|  [Code Files]  [Documents]  [Memories]  [Web Research]  [Task Engine] |
+-----------------------------------------------------------------------+
                                   |
                                   v
                        +----------------------+
                        |   EntityExtractor    |
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        | RelationshipBuilder  |
                        | (Provenance Engine)  |
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        |      GraphStore      |
                        | (PostgreSQL Backend) |
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        |    GraphRetriever    |
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        | ContextPackageBuilder|
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        |     Kora Agent       |
                        +----------------------+
```

---

## 3. Supported Entity & Relationship Types

### Entity Types (`EntityType`)
1. `PERSON`: User, author, developer, team member.
2. `PROJECT`: Codebase, repository, software workspace.
3. `ORGANIZATION`: Organization, vendor, institution.
4. `FILE`: Source code file, asset, config file.
5. `DOCUMENT`: Document, spreadsheet, presentation, PDF, docx, csv.
6. `CODE_SYMBOL`: Class, function, method, interface, struct.
7. `TASK`: Autonomous plan task, goal, workflow job.
8. `TECHNOLOGY`: Language, database, library, framework, tool.
9. `CONCEPT`: Domain concept, architecture pattern, guideline, heading.
10. `WEB_SOURCE`: Domain, URL, web article, external reference.

### Relationship Types (`RelationshipType`)
1. `BELONGS_TO`: Symbol belongs to File, File belongs to Project.
2. `REFERENCES`: Entity references another entity.
3. `DEPENDS_ON`: Component or task depends on module/library/task.
4. `CREATED_BY`: Document/Memory/Code created by Person/User.
5. `RELATED_TO`: General semantic association.
6. `CONTAINS`: File contains Symbol, Project contains File, Doc contains Heading.
7. `IMPLEMENTS`: Class implements Interface/Base.
8. `USES`: Code/Task uses Technology/Tool.
9. `DERIVED_FROM`: Evidence derived from WebSource or Doc.
10. `CONTRADICTS`: Opposing facts, conflicting rules, or incompatible settings.

---

## 4. PostgreSQL Storage Schema
All graph data is stored in PostgreSQL tables (`graph_entities` and `graph_relationships`):

- **`graph_entities`**:
  - `id`: `UUID` Primary Key
  - `entity_type`: `TEXT`
  - `name`: `TEXT`
  - `canonical_name`: `TEXT` (normalized lowercased for fast lookups)
  - `project_id`: `UUID` (Foreign Key to `projects.id` ON DELETE CASCADE, nullable for shared global entities)
  - `source`: `TEXT` (e.g. `file:apps/agent/core/session.py`, `memory:<uuid>`, `web:<url>`, `task:<uuid>`)
  - `confidence`: `FLOAT` (0.0 to 1.0)
  - `metadata`: `JSONB`
  - `created_at`, `updated_at`: `TIMESTAMPTZ`

- **`graph_relationships`**:
  - `id`: `UUID` Primary Key
  - `source_entity_id`: `UUID` (Foreign Key to `graph_entities.id` ON DELETE CASCADE)
  - `relationship_type`: `TEXT`
  - `target_entity_id`: `UUID` (Foreign Key to `graph_entities.id` ON DELETE CASCADE)
  - `project_id`: `UUID` (Foreign Key to `projects.id` ON DELETE CASCADE, nullable)
  - `confidence`: `FLOAT` (0.0 to 1.0)
  - `provenance`: `JSONB` (`{ source_type, file_path, evidence, ... }`)
  - `is_inferred`: `BOOLEAN` (default `FALSE`)
  - `created_at`, `updated_at`: `TIMESTAMPTZ`

---

## 5. Provenance & Inferred Separation
- **Strict Grounding**: Every node and relationship records its exact origin (`provenance`).
- **Inferred Links**: Relationships derived via transitive traversal or heuristic association are explicitly tagged (`is_inferred = True`, lower confidence score).
- **Presentation**: Formatted contexts presented to the LLM explicitly separate `[VERIFIED]` source-backed facts from `[INFERRED]` associations to prevent hallucination.

---

## 6. Stale Relationship Cleanup & Project Isolation
- When a file is modified or deleted, `KnowledgeGraphService.cleanup_file(file_path, project_id)` automatically removes all entities originating from that file and prunes connected edges from the graph.
- All traversals and searches are scoped by `project_id` to enforce strict project isolation.
