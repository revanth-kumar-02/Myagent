import pytest
import asyncio
from core.planner import AgentPlanner, TaskPlan, PlanStepSchema
from core.plan_validator import PlanValidator, plan_validator
from core.state import TaskStepState

@pytest.mark.asyncio
async def test_valid_plan_validation():
    plan = TaskPlan(
        goal="Valid test plan",
        steps=[
            PlanStepSchema(id="step_1", title="Scan workspace", tool="list_directory", dependencies=[]),
            PlanStepSchema(id="step_2", title="Read config", tool="read_file", dependencies=["step_1"])
        ]
    )
    res = plan_validator.validate_plan(plan)
    assert res.valid is True
    assert len(res.errors) == 0

@pytest.mark.asyncio
async def test_invalid_tool_rejection():
    plan = TaskPlan(
        goal="Plan with malicious tool",
        steps=[
            PlanStepSchema(id="step_1", title="Exec hack", tool="unregistered_malicious_tool", dependencies=[])
        ]
    )
    res = plan_validator.validate_plan(plan)
    assert res.valid is False
    assert any("invalid tool" in e for e in res.errors)

@pytest.mark.asyncio
async def test_invalid_dependency_id():
    plan = TaskPlan(
        goal="Plan with missing dependency",
        steps=[
            PlanStepSchema(id="step_1", title="Step 1", tool="list_directory", dependencies=["non_existent_step"])
        ]
    )
    res = plan_validator.validate_plan(plan)
    assert res.valid is False
    assert any("non-existent dependency" in e for e in res.errors)

@pytest.mark.asyncio
async def test_circular_dependency_rejection():
    plan = TaskPlan(
        goal="Plan with circular dependency",
        steps=[
            PlanStepSchema(id="step_1", title="Step 1", tool="list_directory", dependencies=["step_2"]),
            PlanStepSchema(id="step_2", title="Step 2", tool="read_file", dependencies=["step_1"])
        ]
    )
    res = plan_validator.validate_plan(plan)
    assert res.valid is False
    assert any("Circular dependency" in e for e in res.errors)

@pytest.mark.asyncio
async def test_workspace_escape_rejection():
    v = PlanValidator(authorized_roots=["/tmp/safe_dir"])
    plan = TaskPlan(
        goal="Escape boundary",
        steps=[
            PlanStepSchema(
                id="step_1",
                title="Read outside file",
                tool="read_file",
                arguments={"path": "/etc/passwd"},
                dependencies=[]
            )
        ]
    )
    res = v.validate_plan(plan)
    assert res.valid is False
    assert any("escapes authorized workspace" in e for e in res.errors)
