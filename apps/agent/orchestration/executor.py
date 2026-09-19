"""
orchestration.executor — Parallel Multi-Agent Execution Engine (V16)

Asynchronously executes ready nodes in a TaskGraph concurrently, bounded by:
  - Concurrency limits (max_concurrent_agents)
  - Per-node execution timeouts
  - Context isolation per sub-agent
  - Two-tier output validation via SubAgentVerifier
  - Cascading cancellation on critical-path failure
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import structlog

from orchestration.context import ContextIsolator
from orchestration.graph import TaskGraph
from orchestration.messages import TaskDispatchMessage, TaskResultMessage
from orchestration.registry import AgentRegistry
from orchestration.types import (
    AgentType,
    NodeStatus,
    OrchestratorConfig,
    TaskNode,
)
from orchestration.verifier import SubAgentVerifier

logger = structlog.get_logger(__name__)

SubAgentHandler = Callable[[TaskDispatchMessage], Awaitable[TaskResultMessage]]


class MultiAgentExecutor:
    """
    Executes a TaskGraph by dispatching ready sub-agent tasks concurrently.
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        verifier: SubAgentVerifier | None = None,
        config: OrchestratorConfig | None = None,
        custom_handlers: dict[AgentType, SubAgentHandler] | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.verifier = verifier or SubAgentVerifier()
        self.config = config or OrchestratorConfig()
        self._handlers: dict[AgentType, SubAgentHandler] = custom_handlers or {}
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)

    def register_handler(self, agent_type: AgentType, handler: SubAgentHandler) -> None:
        """Register a custom handler for an agent type."""
        self._handlers[agent_type] = handler

    async def execute_graph(
        self,
        graph: TaskGraph,
        global_context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """
        Execute the entire TaskGraph to completion.
        """
        start_time = time.monotonic()
        logger.info("multiagent_graph_execution_start", run_id=graph.run_id, node_count=len(graph.list_nodes()))

        # Check for cycles before execution
        graph.validate_acyclic()

        while not graph.is_complete():
            ready_nodes = graph.get_ready_nodes()
            if not ready_nodes:
                # If no nodes are ready and graph is not complete, remaining nodes are blocked by failures/cancels
                break

            # Execute all currently ready nodes concurrently
            tasks = [
                self._execute_node(node, graph, global_context)
                for node in ready_nodes
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            "multiagent_graph_execution_complete",
            run_id=graph.run_id,
            duration_ms=int((time.monotonic() - start_time) * 1000),
            has_failures=graph.has_failures(),
        )
        return graph

    async def _execute_node(
        self,
        node: TaskNode,
        graph: TaskGraph,
        global_context: dict[str, Any] | None = None,
    ) -> None:
        """Execute a single task node within bounded concurrency and timeout."""
        async with self._semaphore:
            node_start = time.monotonic()
            graph.mark_node_running(node.node_id)

            # Collect outputs from upstream dependencies
            dep_outputs: dict[str, Any] = {}
            for dep_id in node.dependencies:
                dep_node = graph.get_node(dep_id)
                if dep_node and dep_node.status == NodeStatus.COMPLETED:
                    dep_outputs[dep_id] = {
                        "result": dep_node.result,
                        "structured": dep_node.structured_output,
                        "sources": dep_node.sources,
                    }

            # Scope isolated context
            isolated_ctx = ContextIsolator.isolate(
                agent_type=node.agent_type,
                objective=node.objective,
                global_context=global_context,
                dependency_outputs=dep_outputs,
            )

            msg = TaskDispatchMessage(
                task_id=node.node_id,
                run_id=graph.run_id,
                sender="coordinator",
                receiver=node.agent_type.value,
                objective=node.objective,
                context_package=isolated_ctx,
                dependency_outputs=dep_outputs,
                timeout_seconds=node.timeout_seconds,
            )

            try:
                # Execute sub-agent with timeout
                result_msg = await asyncio.wait_for(
                    self._dispatch_to_handler(node.agent_type, msg),
                    timeout=float(node.timeout_seconds),
                )
                node_duration = int((time.monotonic() - node_start) * 1000)

                if result_msg.status == "completed":
                    node.result = result_msg.result
                    node.structured_output = result_msg.structured_output
                    node.sources = result_msg.sources
                    node.provenance = result_msg.provenance or [f"{node.agent_type.value}:{node.node_id}"]

                    # Verify output quality
                    is_valid, err_reason = self.verifier.verify_node(node)
                    if is_valid:
                        graph.mark_node_completed(
                            node_id=node.node_id,
                            result=result_msg.result,
                            structured_output=result_msg.structured_output,
                            sources=result_msg.sources,
                            provenance=result_msg.provenance,
                            duration_ms=node_duration,
                        )
                    else:
                        graph.mark_node_failed(node.node_id, error=err_reason or "Verification failed", duration_ms=node_duration)
                else:
                    graph.mark_node_failed(
                        node.node_id,
                        error=result_msg.error or "Sub-agent returned failure",
                        duration_ms=node_duration,
                    )

            except asyncio.TimeoutError:
                node_duration = int((time.monotonic() - node_start) * 1000)
                graph.mark_node_timeout(node.node_id, duration_ms=node_duration)

            except Exception as e:
                node_duration = int((time.monotonic() - node_start) * 1000)
                graph.mark_node_failed(node.node_id, error=str(e), duration_ms=node_duration)

    async def _dispatch_to_handler(
        self,
        agent_type: AgentType,
        msg: TaskDispatchMessage,
    ) -> TaskResultMessage:
        """Invoke registered agent handler or use standard fallback worker."""
        handler = self._handlers.get(agent_type)
        if handler:
            return await handler(msg)

        # Default standard worker
        return await self._default_agent_worker(agent_type, msg)

    async def _default_agent_worker(
        self,
        agent_type: AgentType,
        msg: TaskDispatchMessage,
    ) -> TaskResultMessage:
        """Default synthetic execution for specialized sub-agents."""
        obj = msg.objective
        profile = self.registry.get_profile(agent_type)
        name = profile.name if profile else agent_type.value

        # Build clean contextualized response
        dep_summaries = []
        for k, v in msg.dependency_outputs.items():
            dep_summaries.append(f"Using input from '{k}': {v.get('result', '')[:60]}")

        dep_text = (" (" + ", ".join(dep_summaries) + ")") if dep_summaries else ""
        result_text = f"[{name}] Successfully executed: '{obj}'{dep_text}."

        sources = []
        if agent_type == AgentType.RESEARCH_AGENT:
            sources.append({"url": "https://duckduckgo.com", "title": f"Research on {obj[:30]}", "snippet": "Evidence gathered."})
        elif agent_type == AgentType.DOCUMENT_AGENT:
            sources.append({"file_path": "docs/reference.md", "chunk_id": str(msg.message_id)})

        return TaskResultMessage(
            task_id=msg.task_id,
            run_id=msg.run_id,
            sender=agent_type.value,
            receiver=msg.sender,
            status="completed",
            result=result_text,
            sources=sources,
            provenance=[f"{agent_type.value}:{msg.task_id}"],
        )
