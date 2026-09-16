import pytest
from core.recovery import FailureClassifier, FailureCategory, RecoveryStrategy
from core.planner import AgentPlanner, PlanStepSchema

def test_failure_classification():
    assert FailureClassifier.classify("Execution timed out after 60s", "terminal") == FailureCategory.TIMEOUT
    assert FailureClassifier.classify("Permission denied for path /etc/shadow", "read_file") == FailureCategory.PERMISSION
    assert FailureClassifier.classify("Invalid argument: missing required parameter 'url'", "browser") == FailureCategory.INVALID_INPUT
    assert FailureClassifier.classify("Command failed with exit code 1", "terminal", exit_code=1) == FailureCategory.TOOL_FAILURE
    assert FailureClassifier.classify("ModuleNotFoundError: No module named 'foo'", "terminal") == FailureCategory.ENVIRONMENT

@pytest.mark.asyncio
async def test_permission_failure_escalation():
    planner = AgentPlanner()
    failed_step = PlanStepSchema(
        id="step_1",
        title="Escalated step",
        description="Write restricted file",
        tool="edit_file",
        permission_level="WRITE"
    )
    decision = await planner.replan(
        goal="Test recovery",
        completed_steps=[],
        failed_step=failed_step,
        failure_category=FailureCategory.PERMISSION,
        error_message="Security rejection",
        tool_output=None
    )
    assert decision.strategy == RecoveryStrategy.ASK_USER
    assert "Permission required" in decision.user_prompt

@pytest.mark.asyncio
async def test_retry_bounds_loop_prevention():
    planner = AgentPlanner()
    failed_step = PlanStepSchema(
        id="step_1",
        title="Failing terminal command",
        description="Run test suite",
        tool="terminal",
        retry_policy={"max_retries": 2}
    )
    decision = await planner.replan(
        goal="Loop test",
        completed_steps=[],
        failed_step=failed_step,
        failure_category=FailureCategory.TOOL_FAILURE,
        error_message="npm test failed",
        tool_output=None,
        retry_count=2
    )
    assert decision.strategy in (RecoveryStrategy.ASK_USER, RecoveryStrategy.ABORT)
    assert decision.strategy != RecoveryStrategy.RETRY

@pytest.mark.asyncio
async def test_plan_modification_for_test_failure():
    planner = AgentPlanner()
    failed_step = PlanStepSchema(
        id="step_3",
        title="Run tests",
        description="Execute pytest suite",
        tool="terminal",
        arguments={"command": "pytest"}
    )
    decision = await planner.replan(
        goal="Fix test",
        completed_steps=[],
        failed_step=failed_step,
        failure_category=FailureCategory.TOOL_FAILURE,
        error_message="FAILED test_app.py::test_calc",
        tool_output=None,
        retry_count=0
    )
    assert decision.strategy == RecoveryStrategy.MODIFY_PLAN
    assert len(decision.new_steps) >= 2
