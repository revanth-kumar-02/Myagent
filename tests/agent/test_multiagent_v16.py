"""
tests.agent.test_multiagent_v16 — Test Suite for Kora Multi-Agent Orchestration (V16)

Verifies:
  1. Agent Registry profiles, tool allowances, and model capabilities
  2. Direct execution without delegation for simple requests
  3. Sequential multi-agent workflow (A -> B)
  4. Parallel multi-agent fan-out/fan-in (A, B -> C)
  5. Dependency handling, topological sorting, and cycle detection
  6. Context and project isolation per sub-agent
  7. Result synthesis, provenance preservation, and contradiction detection
  8. Timeouts, error propagation, and cascading node cancellations
  9. SubAgentVerifier quality checks
 10. End-to-end Coordinator execution and WebSocket broadcasting
 11. Database schema models
"""

import asyncio
import uuid
import pytest

from orchestration.context import ContextIsolator
from orchestration.coordinator import CoordinatorAgent
from orchestration.executor import MultiAgentExecutor
from orchestration.graph import CycleDetectedError, TaskGraph
from orchestration.messages import TaskDispatchMessage, TaskResultMessage
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
from db.schema import AgentCoordinationRunRecord, SubAgentTaskRecord


# ── 1. Agent Registry & Permissions ───────────────────────────────────────────

def test_agent_registry_profiles():
    registry = AgentRegistry()
    profiles = registry.list_profiles()
    assert len(profiles) >= 6

    # Verify Research Agent
    research = registry.get_profile(AgentType.RESEARCH_AGENT)
    assert research is not None
    assert "web_search" in research.capabilities
    assert registry.validate_tool_allowed(AgentType.RESEARCH_AGENT, "duckduckgo_search") is True
    assert registry.validate_tool_allowed(AgentType.RESEARCH_AGENT, "run_terminal_command") is False

    # Verify Coding Agent
    coding = registry.get_profile(AgentType.CODING_AGENT)
    assert coding is not None
    assert "code_generation" in coding.capabilities
    assert registry.validate_tool_allowed(AgentType.CODING_AGENT, "file_write") is True


# ── 2. Direct Execution Without Delegation ────────────────────────────────────

@pytest.mark.asyncio
async def test_coordinator_simple_task_no_delegation():
    coordinator = CoordinatorAgent()

    # Simple greetings or arithmetic
    assert coordinator.should_delegate("Hello Kora") is False
    assert coordinator.should_delegate("What is 5+5?") is False
    assert coordinator.should_delegate("what time is it?") is False

    res = await coordinator.run("Hello Kora")
    assert res.status == "success"
    assert "direct" in res.nodes_executed
    assert "Processed request directly" in res.full_text


# ── 3. Sequential Delegation Workflow ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_sequential_multiagent_execution():
    registry = AgentRegistry()
    executor = MultiAgentExecutor(registry=registry)
    graph = TaskGraph(run_id="seq_test")

    # Step 1: Research
    n1 = TaskNode(
        node_id="step1",
        agent_type=AgentType.RESEARCH_AGENT,
        objective="Find API specifications",
    )
    # Step 2: Code (Depends on Step 1)
    n2 = TaskNode(
        node_id="step2",
        agent_type=AgentType.CODING_AGENT,
        objective="Write Python client based on specs",
        dependencies=["step1"],
    )
    graph.add_node(n1)
    graph.add_node(n2)

    # Execute
    res_graph = await executor.execute_graph(graph)
    assert res_graph.is_complete() is True
    assert res_graph.get_node("step1").status == NodeStatus.COMPLETED
    assert res_graph.get_node("step2").status == NodeStatus.COMPLETED

    # Verify step2 utilized step1 outputs
    res2 = res_graph.get_node("step2").result
    assert "step1" in res2


# ── 4. Parallel Delegation Workflow ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_parallel_multiagent_fan_out():
    registry = AgentRegistry()
    executor = MultiAgentExecutor(registry=registry)
    graph = TaskGraph(run_id="parallel_test")

    # Branch A
    nA = TaskNode(
        node_id="branch_a",
        agent_type=AgentType.RESEARCH_AGENT,
        objective="Research Topic Alpha",
    )
    # Branch B
    nB = TaskNode(
        node_id="branch_b",
        agent_type=AgentType.RESEARCH_AGENT,
        objective="Research Topic Beta",
    )
    # Merge C (Depends on A and B)
    nC = TaskNode(
        node_id="merge_c",
        agent_type=AgentType.GENERAL_TASK_AGENT,
        objective="Compare Alpha and Beta",
        dependencies=["branch_a", "branch_b"],
    )
    graph.add_node(nA)
    graph.add_node(nB)
    graph.add_node(nC)

    # Initial ready nodes should be both branch_a and branch_b
    ready = graph.get_ready_nodes()
    assert len(ready) == 2
    assert {r.node_id for r in ready} == {"branch_a", "branch_b"}

    # Execute
    res_graph = await executor.execute_graph(graph)
    assert res_graph.is_complete() is True
    assert res_graph.get_node("branch_a").status == NodeStatus.COMPLETED
    assert res_graph.get_node("branch_b").status == NodeStatus.COMPLETED
    assert res_graph.get_node("merge_c").status == NodeStatus.COMPLETED


# ── 5. Cycle Detection in TaskGraph ───────────────────────────────────────────

def test_task_graph_cycle_detection():
    graph = TaskGraph()
    n1 = TaskNode(node_id="n1", agent_type=AgentType.RESEARCH_AGENT, objective="Obj 1", dependencies=["n2"])
    n2 = TaskNode(node_id="n2", agent_type=AgentType.CODING_AGENT, objective="Obj 2", dependencies=["n1"])
    graph.add_node(n1)
    graph.add_node(n2)

    with pytest.raises(CycleDetectedError):
        graph.validate_acyclic()


# ── 6. Context Isolation ──────────────────────────────────────────────────────

def test_context_isolation_scoping():
    global_ctx = {
        "project_id": "proj_123",
        "secret_api_key": "sk-12345678",
        "relevant_files": ["src/main.py"],
        "code_context": "def hello(): pass",
        "search_hints": ["fastapi docs"],
        "data_tables": ["users", "orders"],
    }

    # Research Agent receives search hints, but NOT code_context
    ctx_research = ContextIsolator.isolate(AgentType.RESEARCH_AGENT, "Find docs", global_ctx)
    assert "search_hints" in ctx_research
    assert "code_context" not in ctx_research
    assert "secret_api_key" not in ctx_research

    # Coding Agent receives code files, but NOT search hints
    ctx_code = ContextIsolator.isolate(AgentType.CODING_AGENT, "Write code", global_ctx)
    assert "relevant_files" in ctx_code
    assert "code_context" in ctx_code
    assert "search_hints" not in ctx_code


# ── 7. Result Synthesis & Contradiction Detection ──────────────────────────────

def test_synthesis_and_contradiction_detection():
    synthesizer = ResultSynthesizer()

    # Node A says feature is active
    nodeA = TaskNode(
        node_id="nodeA",
        agent_type=AgentType.RESEARCH_AGENT,
        objective="Check auth support",
        status=NodeStatus.COMPLETED,
        result="Authentication is active and enabled by default.",
    )
    # Node B says feature is disabled
    nodeB = TaskNode(
        node_id="nodeB",
        agent_type=AgentType.DOCUMENT_AGENT,
        objective="Check legacy manual",
        status=NodeStatus.COMPLETED,
        result="Authentication is disabled and unsupported.",
    )

    res: SynthesizedResult = synthesizer.synthesize("Check Auth", [nodeA, nodeB])
    assert len(res.nodes_executed) == 2
    assert len(res.contradictions) >= 1
    assert res.contradictions[0].detected is True
    assert "Factual Discrepancies Detected" in res.full_text


# ── 8. Timeout & Cascading Cancellation ───────────────────────────────────────

@pytest.mark.asyncio
async def test_executor_timeout_and_cascading_cancellation():
    registry = AgentRegistry()
    executor = MultiAgentExecutor(registry=registry)

    # Slow custom handler for slow_node that sleeps
    async def slow_handler(msg: TaskDispatchMessage):
        await asyncio.sleep(2.0)
        return TaskResultMessage(task_id=msg.task_id, sender=msg.receiver, receiver=msg.sender, status="completed")

    executor.register_handler(AgentType.RESEARCH_AGENT, slow_handler)

    graph = TaskGraph(run_id="timeout_test")
    # Timeout set to 0.1s
    n_slow = TaskNode(
        node_id="slow_node",
        agent_type=AgentType.RESEARCH_AGENT,
        objective="Slow web fetch",
        timeout_seconds=0.1,
    )
    n_dep = TaskNode(
        node_id="dep_node",
        agent_type=AgentType.CODING_AGENT,
        objective="Depend on slow node",
        dependencies=["slow_node"],
    )
    graph.add_node(n_slow)
    graph.add_node(n_dep)

    res_graph = await executor.execute_graph(graph)
    assert res_graph.is_complete() is True
    assert res_graph.get_node("slow_node").status == NodeStatus.TIMEOUT
    assert res_graph.get_node("dep_node").status == NodeStatus.CANCELLED


# ── 9. SubAgentVerifier Quality Checks ────────────────────────────────────────

def test_subagent_verifier_checks():
    verifier = SubAgentVerifier()

    # Valid node
    valid_node = TaskNode(node_id="v1", agent_type=AgentType.CODING_AGENT, objective="Build", result="Code output")
    ok, err = verifier.verify_node(valid_node)
    assert ok is True
    assert err is None

    # Empty result
    empty_node = TaskNode(node_id="v2", agent_type=AgentType.CODING_AGENT, objective="Build", result="")
    ok, err = verifier.verify_node(empty_node)
    assert ok is False
    assert "empty output" in err

    # Raw traceback
    tb_node = TaskNode(
        node_id="v3",
        agent_type=AgentType.CODING_AGENT,
        objective="Build",
        result="Traceback (most recent call last):\n  File 'x.py', line 1, in <module>",
    )
    ok, err = verifier.verify_node(tb_node)
    assert ok is False
    assert "traceback" in err


# ── 10. Coordinator End-to-End Execution & WebSocket ──────────────────────────

@pytest.mark.asyncio
async def test_coordinator_end_to_end_flow():
    coordinator = CoordinatorAgent()
    ws_messages = []

    async def mock_ws(payload: dict):
        ws_messages.append(payload)

    goal = "Research latest pgvector performance and write code benchmark script"
    assert coordinator.should_delegate(goal) is True

    res = await coordinator.run(goal=goal, ws_send=mock_ws)
    assert res.status == "success"
    assert len(res.nodes_executed) >= 2
    assert "Synthesized Response for Goal" in res.full_text
    assert len(ws_messages) >= 1
    assert ws_messages[0]["type"] == "MULTIAGENT_PLAN_CREATED"


# ── 11. Database Schema Models ────────────────────────────────────────────────

def test_multiagent_database_schema():
    run_rec = AgentCoordinationRunRecord(
        goal="Multi-Agent Benchmark",
        status="completed",
        graph_data={"nodes": 3},
        synthesis_result={"summary": "Done"},
    )
    assert run_rec.status == "completed"

    task_rec = SubAgentTaskRecord(
        agent_type="research_agent",
        objective="Gather stats",
        status="completed",
        dependencies=[],
        input_payload={},
        output_payload={"data": 123},
    )
    assert task_rec.agent_type == "research_agent"
    assert task_rec.status == "completed"
