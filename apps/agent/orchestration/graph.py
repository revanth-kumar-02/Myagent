"""
orchestration.graph — Task Graph DAG Engine (V16)

Represents, validates, and manages execution state across multi-agent task graphs (DAGs).
Supports:
  - Sequential workflows (A -> B -> C)
  - Parallel fan-out / fan-in (A, B, D -> C)
  - Ready-node resolution and topological sorting
  - Cycle detection & acyclicity validation
  - Cascading dependency cancellation upon failure or timeout
"""

from __future__ import annotations

from typing import Any

import structlog

from orchestration.types import NodeStatus, TaskNode

logger = structlog.get_logger(__name__)


class CycleDetectedError(Exception):
    """Raised when circular dependencies exist in the TaskGraph."""


class TaskGraph:
    """
    Directed Acyclic Graph (DAG) managing multi-agent task decomposition and dependencies.
    """

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id
        self._nodes: dict[str, TaskNode] = {}

    def add_node(self, node: TaskNode) -> TaskNode:
        """Add a task node to the graph."""
        self._nodes[node.node_id] = node
        return node

    def get_node(self, node_id: str) -> TaskNode | None:
        """Get a node by its ID."""
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[TaskNode]:
        """List all nodes in insertion order."""
        return list(self._nodes.values())

    def get_ready_nodes(self) -> list[TaskNode]:
        """
        Return nodes that are in PENDING or READY status and whose dependencies are all COMPLETED.
        """
        ready: list[TaskNode] = []
        for node in self._nodes.values():
            if node.status not in (NodeStatus.PENDING, NodeStatus.READY):
                continue

            # Check if all dependency nodes are COMPLETED
            deps_met = True
            for dep_id in node.dependencies:
                dep_node = self._nodes.get(dep_id)
                if not dep_node or dep_node.status != NodeStatus.COMPLETED:
                    deps_met = False
                    break

            if deps_met:
                node.status = NodeStatus.READY
                ready.append(node)

        return ready

    def mark_node_running(self, node_id: str) -> TaskNode | None:
        """Mark a node as RUNNING."""
        node = self.get_node(node_id)
        if node:
            node.status = NodeStatus.RUNNING
        return node

    def mark_node_completed(
        self,
        node_id: str,
        result: str,
        structured_output: dict[str, Any] | None = None,
        sources: list[dict[str, Any]] | None = None,
        provenance: list[str] | None = None,
        duration_ms: int = 0,
    ) -> TaskNode | None:
        """Mark node as COMPLETED with execution results."""
        node = self.get_node(node_id)
        if node:
            node.status = NodeStatus.COMPLETED
            node.result = result
            node.structured_output = structured_output or {}
            node.sources = sources or []
            node.provenance = provenance or [f"{node.agent_type.value}:{node_id}"]
            node.duration_ms = duration_ms
            logger.info("node_completed", node_id=node_id, duration_ms=duration_ms)
        return node

    def mark_node_failed(self, node_id: str, error: str, duration_ms: int = 0) -> TaskNode | None:
        """
        Mark node as FAILED and cascade cancellation to all downstream dependent nodes.
        """
        node = self.get_node(node_id)
        if node:
            node.status = NodeStatus.FAILED
            node.error = error
            node.duration_ms = duration_ms
            logger.warning("node_failed", node_id=node_id, error=error)
            self._cascade_cancel(node_id, reason=f"Upstream dependency '{node_id}' failed: {error}")
        return node

    def mark_node_timeout(self, node_id: str, duration_ms: int = 0) -> TaskNode | None:
        """Mark node as TIMEOUT and cascade cancellation downstream."""
        node = self.get_node(node_id)
        if node:
            node.status = NodeStatus.TIMEOUT
            node.error = f"Node timed out after {node.timeout_seconds}s"
            node.duration_ms = duration_ms
            logger.warning("node_timeout", node_id=node_id)
            self._cascade_cancel(node_id, reason=f"Upstream dependency '{node_id}' timed out")
        return node

    def _cascade_cancel(self, failed_node_id: str, reason: str) -> None:
        """Recursively cancel all nodes that depend directly or indirectly on failed_node_id."""
        for node in self._nodes.values():
            if failed_node_id in node.dependencies and node.status in (NodeStatus.PENDING, NodeStatus.READY):
                node.status = NodeStatus.CANCELLED
                node.error = reason
                logger.info("node_cancelled", node_id=node.node_id, reason=reason)
                self._cascade_cancel(node.node_id, reason=reason)

    def is_complete(self) -> bool:
        """True when every node is in a terminal state."""
        terminal_states = {
            NodeStatus.COMPLETED,
            NodeStatus.FAILED,
            NodeStatus.CANCELLED,
            NodeStatus.TIMEOUT,
        }
        return all(node.status in terminal_states for node in self._nodes.values())

    def has_failures(self) -> bool:
        """True if any node failed or timed out."""
        return any(node.status in (NodeStatus.FAILED, NodeStatus.TIMEOUT) for node in self._nodes.values())

    def validate_acyclic(self) -> None:
        """
        Verify that the graph contains no cycles using Kahn's algorithm.
        Raises CycleDetectedError if a cycle is found.
        """
        in_degree: dict[str, int] = {k: 0 for k in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.node_id] += 1

        queue = [k for k, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1

            for node in self._nodes.values():
                if curr in node.dependencies:
                    in_degree[node.node_id] -= 1
                    if in_degree[node.node_id] == 0:
                        queue.append(node.node_id)

        if visited_count != len(self._nodes):
            raise CycleDetectedError("Circular dependency detected in TaskGraph")

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary for persistence/API transmission."""
        return {
            "run_id": self.run_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "agent_type": n.agent_type.value,
                    "objective": n.objective,
                    "dependencies": n.dependencies,
                    "status": n.status.value,
                    "result": n.result[:200] if n.result else "",
                    "duration_ms": n.duration_ms,
                    "error": n.error,
                }
                for n in self._nodes.values()
            ],
            "is_complete": self.is_complete(),
        }
