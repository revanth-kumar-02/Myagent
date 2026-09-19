"""
orchestration.coordinator — Coordinator Agent (V16)

The primary entry point for Kora's multi-agent system.
Responsibilities:
  1. Goal Analysis: Determines whether multi-agent delegation is beneficial (avoids delegating simple tasks).
  2. Task Decomposition: Breaks complex, multi-domain goals into a structured TaskGraph (DAG).
  3. Sub-Agent Assignment: Maps sub-tasks to specialized agent profiles with dependency tracking.
  4. Execution Orchestration: Runs the graph via MultiAgentExecutor with concurrency control and timeouts.
  5. Result Synthesis & Verification: Detects contradictions, preserves provenance, and verifies the final answer.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Awaitable, Callable

import structlog

from core.types import VerifierVerdict
from observability.tracer import AgentTracer
from observability.types import ComponentType, EventType
from orchestration.executor import MultiAgentExecutor
from orchestration.graph import TaskGraph
from orchestration.registry import AgentRegistry
from orchestration.synthesis import ResultSynthesizer
from orchestration.types import (
    AgentType,
    NodeStatus,
    OrchestratorConfig,
    SynthesizedResult,
    TaskNode,
)
from orchestration.verifier import SubAgentVerifier

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class CoordinatorAgent:
    """
    Central cognitive orchestrator coordinating specialized sub-agents.
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        executor: MultiAgentExecutor | None = None,
        synthesizer: ResultSynthesizer | None = None,
        verifier: SubAgentVerifier | None = None,
        tracer: AgentTracer | None = None,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.config = config or OrchestratorConfig()
        self.verifier = verifier or SubAgentVerifier()
        self.executor = executor or MultiAgentExecutor(registry=self.registry, verifier=self.verifier, config=self.config)
        self.synthesizer = synthesizer or ResultSynthesizer()
        self.tracer = tracer

    def should_delegate(self, goal: str, context: dict[str, Any] | None = None) -> bool:
        """
        Determine whether a goal is sufficiently complex or multi-faceted
        to warrant decomposition into multiple specialized sub-agents.
        """
        if not goal or not goal.strip():
            return False

        clean = goal.strip().lower()

        # 1. Simple queries and direct commands should NOT be delegated
        simple_patterns = [
            r'^(hi|hello|hey|greetings|thanks|thank you)\b',
            r'^what is (\d+[\+\-\*\/]\d+|\d+)\??$',
            r'^(who are you|what can you do)\??$',
            r'^what time is it\??$',
        ]
        for pat in simple_patterns:
            if re.match(pat, clean):
                return False

        # If very short (< 5 words) and has no multi-task indicators, do not delegate
        words = clean.split()
        if len(words) < 5 and not any(kw in clean for kw in ("research and", "compare", "benchmark", "scrape", "analyze")):
            return False

        # 2. Multi-domain, parallel, or complex keywords warrant delegation
        multi_domain_triggers = [
            "research and",
            "and write code",
            "and implement",
            "compare",
            "benchmark",
            "scrape and analyze",
            "extract from document and",
            "simultaneously",
            "in parallel",
            "cross-reference",
        ]
        return any(trig in clean for trig in multi_domain_triggers) or len(words) >= 15

    def decompose(self, goal: str, context: dict[str, Any] | None = None) -> TaskGraph:
        """
        Decompose a complex user goal into a DAG of specialized sub-agent tasks.
        """
        run_id = str(uuid.uuid4())
        graph = TaskGraph(run_id=run_id)
        clean = goal.lower()

        # Pattern 1: Multi-topic comparison / parallel research
        if "compare" in clean or ("in parallel" in clean and "research" in clean):
            n1 = TaskNode(
                node_id="research_a",
                agent_type=AgentType.RESEARCH_AGENT,
                objective=f"Research primary aspects of: {goal}",
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            n2 = TaskNode(
                node_id="research_b",
                agent_type=AgentType.RESEARCH_AGENT,
                objective=f"Research comparative alternatives and nuances of: {goal}",
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            n3 = TaskNode(
                node_id="synthesis_comparison",
                agent_type=AgentType.GENERAL_TASK_AGENT,
                objective=f"Synthesize and compare findings for: {goal}",
                dependencies=["research_a", "research_b"],
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            graph.add_node(n1)
            graph.add_node(n2)
            graph.add_node(n3)
            return graph

        # Pattern 2: Research followed by Code implementation
        if ("research" in clean and ("code" in clean or "implement" in clean or "script" in clean)) or "and write code" in clean:
            n1 = TaskNode(
                node_id="research_spec",
                agent_type=AgentType.RESEARCH_AGENT,
                objective=f"Gather specifications, APIs, and requirements for: {goal}",
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            n2 = TaskNode(
                node_id="coding_implementation",
                agent_type=AgentType.CODING_AGENT,
                objective=f"Write and verify source code implementing: {goal}",
                dependencies=["research_spec"],
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            graph.add_node(n1)
            graph.add_node(n2)
            return graph

        # Pattern 3: Document analysis and Data transformation
        if "document" in clean or "pdf" in clean:
            n1 = TaskNode(
                node_id="doc_extract",
                agent_type=AgentType.DOCUMENT_AGENT,
                objective=f"Extract key data points and sections from documents for: {goal}",
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            n2 = TaskNode(
                node_id="data_analysis",
                agent_type=AgentType.DATA_AGENT,
                objective=f"Analyze and structure extracted document figures for: {goal}",
                dependencies=["doc_extract"],
                timeout_seconds=self.config.default_task_timeout_seconds,
            )
            graph.add_node(n1)
            graph.add_node(n2)
            return graph

        # Default standard 2-step decomposition
        n1 = TaskNode(
            node_id="gather_context",
            agent_type=AgentType.RESEARCH_AGENT if "find" in clean or "search" in clean else AgentType.GENERAL_TASK_AGENT,
            objective=f"Gather initial findings and data for: {goal}",
            timeout_seconds=self.config.default_task_timeout_seconds,
        )
        n2 = TaskNode(
            node_id="execute_solution",
            agent_type=AgentType.GENERAL_TASK_AGENT,
            objective=f"Finalize and execute solution for: {goal}",
            dependencies=["gather_context"],
            timeout_seconds=self.config.default_task_timeout_seconds,
        )
        graph.add_node(n1)
        graph.add_node(n2)
        return graph

    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        ws_send: WSSend | None = None,
    ) -> SynthesizedResult:
        """
        Orchestrate multi-agent execution or execute directly if delegation is unnecessary.
        """
        start_time = time.monotonic()
        trace_id = uuid.uuid4()

        logger.info("coordinator_run_start", goal=goal[:60])

        # 1. Decide if delegation is required
        should_delegate = self.should_delegate(goal, context)

        if not should_delegate:
            # Handle directly without multi-agent overhead
            logger.info("coordinator_executing_directly_no_delegation", goal=goal[:60])
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return SynthesizedResult(
                summary="Direct response without multi-agent delegation.",
                full_text=f"Processed request directly: {goal}",
                provenance={"direct_execution": "coordinator"},
                nodes_executed=["direct"],
                duration_ms=duration_ms,
                status="success",
            )

        # 2. Decompose Goal into TaskGraph DAG
        graph = self.decompose(goal, context)
        nodes = graph.list_nodes()

        # Emit observability trace
        if self.tracer:
            await self.tracer.emit_event(
                event_type=EventType.COORDINATOR_PLAN_STARTED,
                component=ComponentType.ORCHESTRATION,
                trace_id=trace_id,
                payload={"goal": goal, "nodes": [n.node_id for n in nodes]},
            )

        if ws_send is not None:
            await ws_send({
                "type": "MULTIAGENT_PLAN_CREATED",
                "payload": {
                    "run_id": graph.run_id,
                    "goal": goal,
                    "nodes": [{"id": n.node_id, "agent": n.agent_type.value, "objective": n.objective, "deps": n.dependencies} for n in nodes],
                },
            })

        # 3. Execute TaskGraph
        completed_graph = await self.executor.execute_graph(graph, global_context=context)

        # 4. Result Synthesis & Contradiction Detection
        duration_ms = int((time.monotonic() - start_time) * 1000)
        synthesized = self.synthesizer.synthesize(
            goal=goal,
            nodes=completed_graph.list_nodes(),
            duration_ms=duration_ms,
        )

        # 5. Output Verification
        verdict, reason = await self.verifier.verify_synthesis(goal, synthesized)
        if verdict != VerifierVerdict.PASS:
            logger.warning("synthesis_verification_failed", reason=reason)
            synthesized.status = "partial_success"

        # 6. Observability Completion
        if self.tracer:
            await self.tracer.emit_event(
                event_type=EventType.SYNTHESIS_COMPLETED,
                component=ComponentType.ORCHESTRATION,
                trace_id=trace_id,
                duration_ms=duration_ms,
                payload={"status": synthesized.status, "contradictions_count": len(synthesized.contradictions)},
            )

        return synthesized
