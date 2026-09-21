"""
tests.agent.test_visual_workflow_v20 — Test Suite for Visual Workflow Automation (V20)

Verifies:
- Workflow definition, serialization, and deserialization
- Recording workflows with privacy protections & credential masking
- Replaying workflows with dynamic visual grounding and parameterization
- Conditional step evaluation (ELEMENT_EXISTS, TEXT_APPEARS, DIALOG_APPEARS)
- Variable interpolation and secret protection
- Closed-loop verification and branch-on-failure recovery
- Loop prevention guard (max_total_steps threshold)
- PermissionGate enforcement on workflow actions
"""

import json
import pathlib
import pytest
from unittest.mock import AsyncMock

from permissions.gate import PermissionGate
from vision import (
    BoundingBox,
    CaptureOptions,
    ScreenCaptureEngine,
    UIElement,
    UIElementType,
    VerificationStatus,
    VisualAnalysisResult,
    VisualUnderstandingEngine,
)
from vision.workflows import (
    ConditionType,
    StepExecutionRecord,
    VisualActionType,
    VisualConditionEvaluator,
    VisualStepCondition,
    VisualStepVerification,
    VisualWorkflow,
    VisualWorkflowEngine,
    VisualWorkflowRecorder,
    VisualWorkflowReplayer,
    VisualWorkflowStep,
    WorkflowExecutionResult,
    WorkflowStatus,
)


def test_workflow_definition_and_serialization():
    """Test round-trip serialization and deserialization of VisualWorkflow."""
    step1 = VisualWorkflowStep(
        step_id="step_1",
        name="Click Settings",
        action_type=VisualActionType.CLICK,
        target_query="Settings button",
        condition=VisualStepCondition(
            condition_type=ConditionType.ELEMENT_EXISTS,
            target_label="Settings",
        ),
        verification=VisualStepVerification(
            expected_element="Settings Panel",
        ),
    )

    wf = VisualWorkflow(
        workflow_id="wf_test_01",
        name="Test Workflow",
        description="A test automation workflow",
        target_app="Kora App",
        variables={"env": "staging"},
        steps=[step1],
    )

    wf_dict = wf.to_dict()
    assert wf_dict["workflow_id"] == "wf_test_01"
    assert len(wf_dict["steps"]) == 1
    assert wf_dict["steps"][0]["action_type"] == "click"

    restored = VisualWorkflow.from_dict(wf_dict)
    assert restored.workflow_id == "wf_test_01"
    assert restored.name == "Test Workflow"
    assert len(restored.steps) == 1
    assert restored.steps[0].condition is not None
    assert restored.steps[0].condition.condition_type == ConditionType.ELEMENT_EXISTS


def test_visual_workflow_recorder_and_secret_masking(tmp_path: pathlib.Path):
    """Test recorder builds clean workflow and masks passwords/tokens."""
    recorder = VisualWorkflowRecorder(name="Secure Workflow", description="Records user actions safely")

    # Safe variable
    recorder.set_variable("user_name", "alice")
    # Sensitive variable (should be rejected)
    recorder.set_variable("api_key", "secret12345")
    assert "user_name" in recorder.variables
    assert "api_key" not in recorder.variables

    # Click step
    recorder.add_click("Click Login", "Login button")

    # Typing step with password (should be sanitized)
    recorder.add_type("Type Auth", "Password input", "password=supersecretpassword123")

    wf = recorder.build_workflow()
    assert len(wf.steps) == 2
    assert "supersecretpassword123" not in wf.steps[1].input_text
    assert "[REDACTED_SECRET]" in wf.steps[1].input_text

    # File export test
    save_path = tmp_path / "saved_workflow.json"
    recorder.save_to_file(str(save_path))
    assert save_path.exists()


@pytest.mark.asyncio
async def test_visual_workflow_replayer_file_io(tmp_path: pathlib.Path):
    """Test loading workflow from file and replaying through VisualWorkflowReplayer."""
    wf_file = tmp_path / "sample_wf.json"
    sample_wf = VisualWorkflow(
        workflow_id="wf_io_test",
        name="File Replay Workflow",
        description="Replayed from JSON",
        steps=[
            VisualWorkflowStep(
                step_id="s1",
                name="Click Continue",
                action_type=VisualActionType.CLICK,
                target_query="Continue",
            )
        ],
    )
    wf_file.write_text(json.dumps(sample_wf.to_dict()))

    mock_elements = [
        {
            "id": "btn_cont",
            "type": "button",
            "label": "Continue",
            "bbox": {"x": 200, "y": 400, "width": 120, "height": 40},
            "confidence": 0.99,
        }
    ]

    replayer = VisualWorkflowReplayer()
    result = await replayer.replay(str(wf_file), mock_pre_elements=mock_elements)

    assert result.status == WorkflowStatus.SUCCESS
    assert len(result.step_records) == 1
    assert result.step_records[0].grounded_coordinates == (260, 420)


@pytest.mark.asyncio
async def test_visual_workflow_engine_execution_and_grounding():
    """Test execution adapts dynamically to UI elements and resolves center coordinates."""
    engine = VisualWorkflowEngine()

    mock_elements = [
        {
            "id": "btn_settings",
            "type": "button",
            "label": "Settings",
            "bbox": {"x": 100, "y": 200, "width": 80, "height": 40},
            "confidence": 0.98,
        },
        {
            "id": "inp_filter",
            "type": "input_field",
            "label": "Filter Repositories",
            "bbox": {"x": 300, "y": 200, "width": 200, "height": 40},
            "confidence": 0.95,
        },
    ]

    wf = VisualWorkflow(
        workflow_id="wf_exec_01",
        name="Dynamic Grounding Test",
        description="Testing adaptive grounding",
        variables={"repo": "Kora"},
        steps=[
            VisualWorkflowStep(
                step_id="step_1",
                name="Open Settings",
                action_type=VisualActionType.CLICK,
                target_query="Settings button",
            ),
            VisualWorkflowStep(
                step_id="step_2",
                name="Filter by Repo",
                action_type=VisualActionType.TYPE,
                target_query="Filter Repositories",
                input_text="{{repo}}",
            ),
        ],
    )

    result = await engine.execute_workflow(wf, mock_pre_elements=mock_elements)

    assert result.status == WorkflowStatus.SUCCESS
    assert len(result.step_records) == 2
    # Step 1: Center of (100, 200, 80, 40) is (140, 220)
    assert result.step_records[0].grounded_coordinates == (140, 220)
    # Step 2: Center of (300, 200, 200, 40) is (400, 220)
    assert result.step_records[1].grounded_coordinates == (400, 220)


def test_conditional_step_evaluation():
    """Test VisualConditionEvaluator across multiple condition types."""
    evaluator = VisualConditionEvaluator()

    elements = [
        UIElement(
            element_id="btn_ok",
            element_type=UIElementType.BUTTON,
            label="OK",
            bounding_box=BoundingBox(x=10, y=10, width=50, height=20),
        ),
        UIElement(
            element_id="dlg_err",
            element_type=UIElementType.DIALOG,
            label="Error Dialog",
            bounding_box=BoundingBox(x=100, y=100, width=300, height=200),
        ),
    ]

    analysis = VisualAnalysisResult(
        analysis_id="an_1",
        summary="Error dialog displayed.",
        description="Application crashed with error.",
        detected_elements=elements,
        detected_text=["Error", "Crash", "OK"],
        active_window="Crash Reporter",
    )

    # 1. ELEMENT_EXISTS
    cond_elem = VisualStepCondition(condition_type=ConditionType.ELEMENT_EXISTS, target_label="OK")
    assert evaluator.evaluate(cond_elem, analysis) is True

    # 2. DIALOG_APPEARS
    cond_dlg = VisualStepCondition(condition_type=ConditionType.DIALOG_APPEARS)
    assert evaluator.evaluate(cond_dlg, analysis) is True

    # 3. TEXT_APPEARS
    cond_txt = VisualStepCondition(condition_type=ConditionType.TEXT_APPEARS, expected_text="crash")
    assert evaluator.evaluate(cond_txt, analysis) is True

    # 4. Negation
    cond_neg = VisualStepCondition(condition_type=ConditionType.ELEMENT_EXISTS, target_label="NonExistent", negate=True)
    assert evaluator.evaluate(cond_neg, analysis) is True


@pytest.mark.asyncio
async def test_variable_interpolation_and_safety():
    """Test variable interpolation with parameter overrides and secret rejection."""
    engine = VisualWorkflowEngine()

    mock_elements = [
        {
            "id": "inp_query",
            "type": "input_field",
            "label": "Search Box",
            "bbox": {"x": 100, "y": 100, "width": 100, "height": 30},
            "confidence": 0.95,
        }
    ]

    wf = VisualWorkflow(
        workflow_id="wf_var_01",
        name="Variable Test",
        description="Tests variable templating",
        variables={"query": "default_search", "password": "forbidden_secret"},
        steps=[
            VisualWorkflowStep(
                step_id="s1",
                name="Type Query",
                action_type=VisualActionType.TYPE,
                target_query="Search Box",
                input_text="search: {{query}} - {{password}}",
            )
        ],
    )

    res = await engine.execute_workflow(
        wf,
        runtime_variables={"query": "autonomous agents"},
        mock_pre_elements=mock_elements,
    )

    assert res.status == WorkflowStatus.SUCCESS
    # Variable {{query}} should be replaced, but {{password}} should NOT be interpolated
    assert res.variables_used["query"] == "autonomous agents"


@pytest.mark.asyncio
async def test_closed_loop_verification_and_retry_recovery():
    """Test step verification failure triggers branching recovery."""
    engine = VisualWorkflowEngine()

    mock_elements = [
        {
            "id": "btn_trigger",
            "type": "button",
            "label": "Trigger Action",
            "bbox": {"x": 50, "y": 50, "width": 100, "height": 30},
            "confidence": 0.99,
        }
    ]

    wf = VisualWorkflow(
        workflow_id="wf_recovery_01",
        name="Branching Recovery Test",
        description="Tests branching on failure",
        steps=[
            VisualWorkflowStep(
                step_id="step_fail",
                name="Failing Step",
                action_type=VisualActionType.CLICK,
                target_query="Trigger Action",
                max_retries=1,
                verification=VisualStepVerification(expected_element="Nonexistent Verification Target"),
                on_failure_branch_to_step="step_recovery",
            ),
            VisualWorkflowStep(
                step_id="step_skipped",
                name="Skipped Step",
                action_type=VisualActionType.CLICK,
                target_query="Skipped",
            ),
            VisualWorkflowStep(
                step_id="step_recovery",
                name="Recovery Step",
                action_type=VisualActionType.CLICK,
                target_query="Trigger Action",
            ),
        ],
    )

    res = await engine.execute_workflow(wf, mock_pre_elements=mock_elements)
    assert res.status == WorkflowStatus.SUCCESS
    # We should have executed step_fail (which failed and branched) then step_recovery
    step_ids = [r.step_id for r in res.step_records]
    assert "step_fail" in step_ids
    assert "step_recovery" in step_ids
    assert "step_skipped" not in step_ids


@pytest.mark.asyncio
async def test_infinite_loop_prevention():
    """Test max_total_steps prevents infinite branching loops."""
    engine = VisualWorkflowEngine(max_total_steps=5)

    mock_elements = [
        {
            "id": "btn_loop",
            "type": "button",
            "label": "Loop Action",
            "bbox": {"x": 50, "y": 50, "width": 100, "height": 30},
            "confidence": 0.99,
        }
    ]

    # Cyclical workflow that keeps failing and branching to step 1
    wf = VisualWorkflow(
        workflow_id="wf_loop",
        name="Infinite Loop Workflow",
        description="Tests loop limit",
        steps=[
            VisualWorkflowStep(
                step_id="step_1",
                name="Step 1",
                action_type=VisualActionType.CLICK,
                target_query="Loop Action",
                max_retries=0,
                verification=VisualStepVerification(expected_element="Missing Target"),
                on_failure_branch_to_step="step_2",
            ),
            VisualWorkflowStep(
                step_id="step_2",
                name="Step 2",
                action_type=VisualActionType.CLICK,
                target_query="Loop Action",
                max_retries=0,
                verification=VisualStepVerification(expected_element="Missing Target"),
                on_failure_branch_to_step="step_1",
            ),
        ],
    )

    res = await engine.execute_workflow(wf, mock_pre_elements=mock_elements)
    assert res.status == WorkflowStatus.FAILED
    assert "Loop prevention triggered" in (res.error_message or "")
    assert len(res.step_records) == 5


@pytest.mark.asyncio
async def test_permission_gate_enforcement_in_workflow():
    """Test PermissionGate blocks unauthorized high-impact workflow steps."""
    gate = PermissionGate(ws_send=None)  # No WS client -> rejects HIGH_IMPACT_ACTION
    engine = VisualWorkflowEngine(permission_gate=gate)

    mock_elements = [
        {
            "id": "btn_del",
            "type": "button",
            "label": "Delete Cluster",
            "bbox": {"x": 100, "y": 100, "width": 120, "height": 40},
            "confidence": 0.99,
        }
    ]

    wf = VisualWorkflow(
        workflow_id="wf_perm",
        name="Permission Guard Test",
        description="Tests permission check in workflow",
        steps=[
            VisualWorkflowStep(
                step_id="s1",
                name="High Impact Delete Click",
                action_type=VisualActionType.CLICK,
                target_query="Delete Cluster",
            )
        ],
    )

    res = await engine.execute_workflow(wf, mock_pre_elements=mock_elements)
    assert res.status == WorkflowStatus.FAILED
    assert "Permission denied" in (res.error_message or "")
    assert res.step_records[0].executed is False
