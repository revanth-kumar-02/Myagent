"""
personal.graph_bridge — Personal Knowledge Graph Bridge (V17)

Integrates personal goals, decisions, milestones, and user preferences
with Kora's central Knowledge Graph (GraphStore).

Registers and queries semantic user relationships:
  - Project -> supports -> Goal
  - Task -> contributes_to -> Goal
  - Decision -> affects -> Project / Goal
  - Person (User) -> prefers -> Concept / Technology
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from graph.store import GraphStore
from graph.types import (
    EntityType,
    GraphEntityRecord,
    GraphRelationshipRecord,
    RelationshipType,
)

logger = structlog.get_logger(__name__)


class PersonalKnowledgeBridge:
    """
    Connects personal goals and decisions into the global Knowledge Graph.
    """

    def __init__(self, graph_store: GraphStore | None = None) -> None:
        self.store = graph_store or GraphStore()

    async def register_goal(
        self,
        goal_id: uuid.UUID,
        title: str,
        project_id: uuid.UUID | None = None,
    ) -> GraphEntityRecord:
        """Register a goal as a concept/task entity in the graph."""
        entity = GraphEntityRecord(
            entity_id=goal_id,
            name=title,
            entity_type=EntityType.CONCEPT,
            source=f"goal:{goal_id}",
            project_id=project_id,
            metadata={"is_goal": True, "title": title},
        )
        return await self.store.upsert_entity(entity)

    async def link_project_supports_goal(
        self,
        project_id: uuid.UUID,
        project_name: str,
        goal_id: uuid.UUID,
        goal_title: str,
    ) -> GraphRelationshipRecord:
        """Create a relationship: Project -> RELATED_TO (supports) -> Goal."""
        # Ensure project entity exists
        found = await self.store.find_entities(name=project_name, entity_type=EntityType.PROJECT, project_id=project_id)
        if found:
            proj_ent = found[0]
        else:
            proj_ent = await self.store.upsert_entity(
                GraphEntityRecord(
                    entity_id=project_id,
                    name=project_name,
                    entity_type=EntityType.PROJECT,
                    source=f"project:{project_id}",
                    project_id=project_id,
                )
            )

        # Ensure goal entity exists
        goal_ent = await self.store.get_entity(goal_id)
        if not goal_ent:
            goal_ent = await self.register_goal(goal_id, goal_title, project_id)

        rel = GraphRelationshipRecord(
            source_entity_id=proj_ent.entity_id,
            relationship_type=RelationshipType.RELATED_TO,
            target_entity_id=goal_ent.entity_id,
            project_id=project_id,
            confidence=1.0,
            provenance={"relation": "supports_goal"},
        )
        return await self.store.upsert_relationship(rel)

    async def link_task_contributes_to_goal(
        self,
        task_id: uuid.UUID,
        task_goal: str,
        goal_id: uuid.UUID,
        goal_title: str,
        project_id: uuid.UUID | None = None,
    ) -> GraphRelationshipRecord:
        """Create a relationship: Task -> RELATED_TO -> Goal."""
        task_ent = await self.store.get_entity(task_id)
        if not task_ent:
            task_ent = await self.store.upsert_entity(
                GraphEntityRecord(
                    entity_id=task_id,
                    name=task_goal,
                    entity_type=EntityType.TASK,
                    source=f"task:{task_id}",
                    project_id=project_id,
                )
            )

        goal_ent = await self.store.get_entity(goal_id)
        if not goal_ent:
            goal_ent = await self.register_goal(goal_id, goal_title, project_id)

        rel = GraphRelationshipRecord(
            source_entity_id=task_ent.entity_id,
            relationship_type=RelationshipType.RELATED_TO,
            target_entity_id=goal_ent.entity_id,
            project_id=project_id,
            confidence=1.0,
            provenance={"relation": "contributes_to_goal"},
        )
        return await self.store.upsert_relationship(rel)

    async def link_decision_affects_project(
        self,
        decision_id: uuid.UUID,
        decision_text: str,
        project_id: uuid.UUID,
        project_name: str,
    ) -> GraphRelationshipRecord:
        """Create a relationship: Decision (Concept) -> RELATED_TO (affects) -> Project."""
        dec_ent = await self.store.get_entity(decision_id)
        if not dec_ent:
            dec_ent = await self.store.upsert_entity(
                GraphEntityRecord(
                    entity_id=decision_id,
                    name=f"Decision: {decision_text[:40]}",
                    entity_type=EntityType.CONCEPT,
                    source=f"decision:{decision_id}",
                    project_id=project_id,
                )
            )

        proj_ent = await self.store.get_entity(project_id)
        if not proj_ent:
            proj_ent = await self.store.upsert_entity(
                GraphEntityRecord(
                    entity_id=project_id,
                    name=project_name,
                    entity_type=EntityType.PROJECT,
                    source=f"project:{project_id}",
                    project_id=project_id,
                )
            )

        rel = GraphRelationshipRecord(
            source_entity_id=dec_ent.entity_id,
            relationship_type=RelationshipType.RELATED_TO,
            target_entity_id=proj_ent.entity_id,
            project_id=project_id,
            confidence=1.0,
            provenance={"relation": "decision_affects_project"},
        )
        return await self.store.upsert_relationship(rel)

