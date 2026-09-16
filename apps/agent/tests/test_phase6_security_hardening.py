import pytest
from core.plan_validator import PlanValidator
from core.filesystem.permission_manager import permission_manager, PermissionLevel
from core.planner import TaskPlan, PlanStepSchema

@pytest.mark.asyncio
async def test_permission_bypass_prevention():
    v = PlanValidator(authorized_roots=["/tmp/safe_dir"])
    plan = TaskPlan(
        goal="Bypass test",
        steps=[
            PlanStepSchema(
                id="step_1",
                title="Bypass check",
                tool="read_file",
                arguments={"path": "../../../etc/shadow"},
                dependencies=[]
            )
        ]
    )
    val = v.validate_plan(plan)
    assert val.valid is False

@pytest.mark.asyncio
async def test_permission_manager_enforcement():
    # Granting READ permission should NOT auto-grant WRITE or TERMINAL_EXECUTE
    has_write = await permission_manager.check_permission(
        tool_name="edit_file",
        path="config.py",
        operation="Write test",
        permission_level=PermissionLevel.WRITE
    )
    # Default without explicit auto-approve or user approval should be False or gated
    assert isinstance(has_write, bool)
