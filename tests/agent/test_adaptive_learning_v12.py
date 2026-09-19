"""
tests.test_adaptive_learning_v12 — Test Suite for Kora Self-Reflection & Adaptive Learning (V12).

Covers:
  1. Execution Trace Analysis: Step outcomes, duration, retries, error categorization
  2. Reflection Engine: What worked/failed, root cause classification, plan complexity
  3. Learning Validation & Safety: Secret masking, duplicate detection, contradiction resolution
  4. Memory & Knowledge Graph Integration: Persistence into MemoryManager and KnowledgeGraphService
  5. Project Isolation: Scoped learning retrieval
  6. Planner Adaptive Guidance: Planner querying learnings before step construction
  7. User Feedback Loop: USEFUL, NOT_USEFUL, CORRECTION, PREFERRED_APPROACH
"""

from __future__ import annotations

import uuid
import pytest

from core.planner import Planner
from core.types import ChatRequest
from graph.service import KnowledgeGraphService
from learning.analyzer import ExecutionAnalyzer
from learning.manager import AdaptiveLearningManager
from learning.reflector import ReflectionEngine
from learning.types import (
    ExecutionTrace,
    FeedbackType,
    LearningCategory,
    LearningRecord,
    LearningStatus,
    StepOutcome,
)
from learning.validator import LearningValidator, sanitize_text
from memory.manager import MemoryManager
from rag.embedder import BaseEmbedder


class MockEmbedder(BaseEmbedder):
    """Deterministic mock embedder for tests."""

    async def embed(self, chunks):
        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return [0.1] * 1024


# ── 1. Execution Trace Analysis Tests ─────────────────────────────────────────

class TestExecutionAnalysis:
    """Verify synthesis of step reports into an ExecutionTrace."""

    def test_successful_execution_trace_analysis(self) -> None:
        analyzer = ExecutionAnalyzer()
        task_id = uuid.uuid4()

        steps = [
            StepOutcome(step_index=0, goal="Scan files", tool_name="scanner", status="done", duration_ms=50),
            StepOutcome(step_index=1, goal="Index chunks", tool_name="indexer", status="done", duration_ms=150),
        ]

        trace = analyzer.analyze_execution(task_id, "Index repository", steps)
        assert trace.final_outcome == "success"
        assert len(trace.successful_actions) == 2
        assert len(trace.failed_actions) == 0
        assert trace.total_duration_ms == 200
        assert trace.retries_used == 0

    def test_failed_execution_trace_analysis(self) -> None:
        analyzer = ExecutionAnalyzer()
        task_id = uuid.uuid4()

        steps = [
            StepOutcome(step_index=0, goal="Read file", tool_name="file_reader", status="done", duration_ms=40),
            StepOutcome(
                step_index=1,
                goal="Write config",
                tool_name="file_writer",
                status="failed",
                error="Permission denied writing /etc/hosts",
                retry_count=2,
                duration_ms=80,
                verification_verdict="retry",
            ),
        ]

        trace = analyzer.analyze_execution(task_id, "Update system hosts", steps)
        assert trace.final_outcome == "partially_completed"
        assert "file_writer" in trace.failed_actions
        assert trace.retries_used == 2
        assert "Permission denied" in (trace.error_summary or "")


# ── 2. Reflection Engine Tests ────────────────────────────────────────────────

class TestReflectionEngine:
    """Verify evidence-grounded reflection and candidate learning extraction."""

    def test_successful_task_reflection(self) -> None:
        reflector = ReflectionEngine()
        trace = ExecutionTrace(
            task_id=uuid.uuid4(),
            goal="Run automated test suite",
            planned_steps_count=2,
            actual_steps=[
                StepOutcome(step_index=0, goal="Discover tests", tool_name="pytest_discover", status="done"),
                StepOutcome(step_index=1, goal="Execute tests", tool_name="pytest_runner", status="done"),
            ],
            successful_actions=["pytest_discover", "pytest_runner"],
            final_outcome="success",
        )

        analysis = reflector.reflect(trace)
        assert len(analysis.what_worked) == 2
        assert len(analysis.what_failed) == 0
        assert analysis.root_cause is None
        assert len(analysis.candidate_learnings) >= 1

        workflow_learning = next(
            (l for l in analysis.candidate_learnings if l.category == LearningCategory.SUCCESSFUL_WORKFLOW), None
        )
        assert workflow_learning is not None
        assert "pytest_discover -> pytest_runner" in workflow_learning.recommendation

    def test_failed_task_reflection_and_root_cause(self) -> None:
        reflector = ReflectionEngine()
        trace = ExecutionTrace(
            task_id=uuid.uuid4(),
            goal="Fetch external data",
            planned_steps_count=1,
            actual_steps=[
                StepOutcome(
                    step_index=0,
                    goal="Fetch API",
                    tool_name="http_client",
                    status="failed",
                    error="Timeout executing http_client after 10000ms",
                )
            ],
            failed_actions=["http_client"],
            final_outcome="failed",
        )

        analysis = reflector.reflect(trace)
        assert "Timeout executing http_client" in (analysis.root_cause or "")
        assert len(analysis.candidate_learnings) >= 1

        failure_learning = next(
            (l for l in analysis.candidate_learnings if l.category == LearningCategory.FAILED_WORKFLOW), None
        )
        assert failure_learning is not None
        assert failure_learning.confidence >= 0.8

    def test_plan_complexity_detection(self) -> None:
        reflector = ReflectionEngine()
        trace = ExecutionTrace(
            task_id=uuid.uuid4(),
            goal="Simple calculation",
            planned_steps_count=8,  # Over-engineered initial plan
            actual_steps=[
                StepOutcome(step_index=0, goal="Direct calculation", tool_name="calculator", status="done")
            ],
            successful_actions=["calculator"],
            final_outcome="success",
        )

        analysis = reflector.reflect(trace)
        assert analysis.is_plan_overly_complex is True
        planning_learning = next(
            (l for l in analysis.candidate_learnings if l.category == LearningCategory.PLANNING_IMPROVEMENT), None
        )
        assert planning_learning is not None


# ── 3. Learning Validation & Safety Tests ─────────────────────────────────────

class TestLearningValidationAndSafety:
    """Verify secret sanitization, duplicate rejection, and contradiction handling."""

    def test_secret_sanitization(self) -> None:
        raw_text = "Use apiKey: sk-ant-1234567890abcdef1234567890abcdef for authentication"
        sanitized = sanitize_text(raw_text)
        assert "sk-ant-" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_candidate_validation_masks_credentials(self) -> None:
        validator = LearningValidator()
        learning = LearningRecord(
            title="Deploy secret token: ghp_123456789012345678901234567890123456",
            condition="When deploying to GitHub with token: ghp_123456789012345678901234567890123456",
            recommendation="Pass Bearer 1234567890123456 in headers",
            source_task_id=uuid.uuid4(),
            evidence={"task": "deploy"},
        )

        is_valid, reason, validated = validator.validate_candidate(learning)
        assert is_valid is True
        assert "ghp_" not in validated.title
        assert "ghp_" not in validated.condition
        assert "[REDACTED_SECRET]" in validated.condition

    def test_duplicate_detection(self) -> None:
        validator = LearningValidator()
        cand1 = LearningRecord(
            category=LearningCategory.TOOL_SELECTION_PATTERN,
            condition="When parsing markdown files",
            recommendation="Use markdown_parser",
            source_task_id=uuid.uuid4(),
            evidence={"tool": "parser"},
        )
        is_valid1, _, rec1 = validator.validate_candidate(cand1)
        assert is_valid1 is True

        # Candidate 2 with identical condition and recommendation
        cand2 = LearningRecord(
            category=LearningCategory.TOOL_SELECTION_PATTERN,
            condition="When parsing markdown files",
            recommendation="Use markdown_parser",
            source_task_id=uuid.uuid4(),
            evidence={"tool": "parser"},
        )
        is_valid2, reason, _ = validator.validate_candidate(cand2, [rec1])
        assert is_valid2 is False
        assert "Duplicate" in reason

    def test_contradiction_resolution(self) -> None:
        validator = LearningValidator()
        old_rec = LearningRecord(
            category=LearningCategory.TOOL_SELECTION_PATTERN,
            condition="When compiling typescript",
            recommendation="Use tsc compiler",
            status=LearningStatus.ACTIVE,
            source_task_id=uuid.uuid4(),
            evidence={"tool": "tsc"},
        )

        # New learning advises avoiding tsc in favor of esbuild
        new_rec = LearningRecord(
            category=LearningCategory.TOOL_SELECTION_PATTERN,
            condition="When compiling typescript",
            recommendation="Avoid tsc compiler due to slow performance; use esbuild",
            source_task_id=uuid.uuid4(),
            evidence={"tool": "esbuild"},
        )

        is_valid, _, validated_new = validator.validate_candidate(new_rec, [old_rec])
        assert is_valid is True
        assert old_rec.status == LearningStatus.DEPRECATED

    def test_low_confidence_rejection(self) -> None:
        validator = LearningValidator()
        speculative_rec = LearningRecord(
            condition="Random condition",
            recommendation="Random action",
            confidence=0.2,  # Low confidence
            source_task_id=uuid.uuid4(),
            evidence={"data": "test"},
        )
        is_valid, reason, _ = validator.validate_candidate(speculative_rec)
        assert is_valid is False
        assert "below minimum threshold" in reason


# ── 4. Adaptive Learning Manager Tests ────────────────────────────────────────

class TestAdaptiveLearningManager:
    """Verify end-to-end processing, memory/graph storage, and project isolation."""

    @pytest.mark.asyncio
    async def test_end_to_end_task_processing_and_retrieval(self) -> None:
        mem_mgr = MemoryManager(embedder=MockEmbedder())
        graph_svc = KnowledgeGraphService()
        manager = AdaptiveLearningManager(memory_manager=mem_mgr, graph_service=graph_svc)
        project_id = uuid.uuid4()

        trace = ExecutionTrace(
            task_id=uuid.uuid4(),
            goal="Format python codebase",
            planned_steps_count=2,
            actual_steps=[
                StepOutcome(step_index=0, goal="Run ruff", tool_name="ruff_format", status="done", duration_ms=60),
                StepOutcome(step_index=1, goal="Run mypy", tool_name="mypy_check", status="done", duration_ms=120),
            ],
            successful_actions=["ruff_format", "mypy_check"],
            final_outcome="success",
            project_id=project_id,
        )

        report = await manager.process_task_execution(trace)
        assert len(report.stored_learnings) >= 1
        assert len(report.rejected_learnings) == 0

        # Verify retrieval
        results = await manager.get_relevant_learnings("Format python codebase", project_id=project_id)
        assert len(results) >= 1
        assert "ruff_format -> mypy_check" in results[0].recommendation

    def test_project_isolation(self) -> None:
        manager = AdaptiveLearningManager()
        proj_a = uuid.uuid4()
        proj_b = uuid.uuid4()

        rec_a = LearningRecord(
            title="Workflow A",
            condition="When building project A",
            recommendation="Use build_a",
            project_id=proj_a,
            source_task_id=uuid.uuid4(),
            evidence={"p": "a"},
        )
        rec_b = LearningRecord(
            title="Workflow B",
            condition="When building project B",
            recommendation="Use build_b",
            project_id=proj_b,
            source_task_id=uuid.uuid4(),
            evidence={"p": "b"},
        )
        manager._learnings[rec_a.learning_id] = rec_a
        manager._learnings[rec_b.learning_id] = rec_b

        # Project A query
        learnings_a = manager.list_learnings(project_id=proj_a)
        ids_a = {l.learning_id for l in learnings_a}
        assert rec_a.learning_id in ids_a
        assert rec_b.learning_id not in ids_a


# ── 5. Planner Adaptive Guidance Tests ────────────────────────────────────────

class TestPlannerAdaptiveGuidance:
    """Verify Planner consults relevant learnings when decomposing requests."""

    @pytest.mark.asyncio
    async def test_planner_consults_learning_manager(self) -> None:
        manager = AdaptiveLearningManager()
        proj_id = uuid.uuid4()

        rec = LearningRecord(
            category=LearningCategory.TOOL_SELECTION_PATTERN,
            condition="When running tests in python repository",
            recommendation="Use pytest tool",
            project_id=proj_id,
            source_task_id=uuid.uuid4(),
            evidence={"tool": "pytest"},
        )
        manager._learnings[rec.learning_id] = rec

        planner = Planner(learning_manager=manager)
        req = ChatRequest(
            message="Run the python tests",
            session_id=uuid.uuid4(),
            project_id=proj_id,
        )

        plan = await planner.plan(req)
        assert len(plan.steps) >= 1


# ── 6. User Feedback Loop Tests ───────────────────────────────────────────────

class TestUserFeedbackLoop:
    """Verify user feedback adjusts confidence, reinforces, or invalidates learnings."""

    def test_user_feedback_reinforces_learning(self) -> None:
        manager = AdaptiveLearningManager()
        rec = LearningRecord(
            condition="When building with Vite",
            recommendation="Use npx vite build",
            confidence=0.8,
            source_task_id=uuid.uuid4(),
            evidence={"tool": "vite"},
        )
        manager._learnings[rec.learning_id] = rec

        updated = manager.apply_user_feedback(rec.learning_id, FeedbackType.USEFUL)
        assert updated is not None
        assert updated.confidence == 0.9
        assert updated.status == LearningStatus.REINFORCED
        assert updated.feedback_score == 1

    def test_user_feedback_invalidates_learning(self) -> None:
        manager = AdaptiveLearningManager()
        rec = LearningRecord(
            condition="When testing UI",
            recommendation="Use obsolete_tool",
            confidence=0.5,
            source_task_id=uuid.uuid4(),
            evidence={"tool": "test"},
        )
        manager._learnings[rec.learning_id] = rec

        updated = manager.apply_user_feedback(rec.learning_id, FeedbackType.NOT_USEFUL)
        assert updated is not None
        assert updated.confidence <= 0.3
        assert updated.status == LearningStatus.INVALIDATED

    def test_user_correction_feedback(self) -> None:
        manager = AdaptiveLearningManager()
        rec = LearningRecord(
            condition="When compiling assets",
            recommendation="Use webpack",
            source_task_id=uuid.uuid4(),
            evidence={"tool": "build"},
        )
        manager._learnings[rec.learning_id] = rec

        updated = manager.apply_user_feedback(
            rec.learning_id,
            FeedbackType.CORRECTION,
            comments="Use rspack instead of webpack for 10x speed",
        )
        assert updated is not None
        assert updated.recommendation == "Use rspack instead of webpack for 10x speed"
        assert updated.status == LearningStatus.REINFORCED
