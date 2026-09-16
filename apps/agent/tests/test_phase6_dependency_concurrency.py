import pytest
import asyncio
import time
from core.dag_scheduler import DAGScheduler
from core.planner import TaskPlan, PlanStepSchema
from core.state import ExecutionContext, TaskStepState
from core.verifier import AgentVerifier
from core.tools.registry import ToolResult

from db.session import init_db
from core.verifier import VerificationResult

class FastMockVerifier:
    async def verify_step(self, goal, title, output):
        return VerificationResult(success=True, reason="Fast verify", score=1.0)

@pytest.mark.asyncio
async def test_sequential_task_execution():
    await init_db()
    scheduler = DAGScheduler(max_concurrent=3)
    ctx = ExecutionContext(task_id="task_seq", goal="Sequential execution test")
    plan = TaskPlan(
        goal="Sequential test",
        steps=[
            PlanStepSchema(id="step_1", title="First step", tool="list_directory", dependencies=[]),
            PlanStepSchema(id="step_2", title="Second step", tool="read_file", dependencies=["step_1"])
        ]
    )

    execution_order = []

    async def mock_executor(step, context):
        execution_order.append(step.step_id)
        await asyncio.sleep(0.05)
        return ToolResult(success=True, data=f"Data from {step.step_id}")

    verifier = FastMockVerifier()
    res_ctx = await scheduler.execute_dag_plan(ctx, plan, verifier, mock_executor)

    assert res_ctx.current_state.value in ("completed", "executing")
    assert execution_order == ["step_1", "step_2"]

@pytest.mark.asyncio
async def test_parallel_independent_tasks():
    await init_db()
    scheduler = DAGScheduler(max_concurrent=3)
    ctx = ExecutionContext(task_id="task_parallel", goal="Parallel execution test")
    plan = TaskPlan(
        goal="Parallel test",
        steps=[
            PlanStepSchema(id="step_1", title="Indep 1", tool="git_status", dependencies=[]),
            PlanStepSchema(id="step_2", title="Indep 2", tool="list_directory", dependencies=[]),
            PlanStepSchema(id="step_3", title="Indep 3", tool="search_files", dependencies=[])
        ]
    )

    active_counts = []
    current_active = 0
    lock = asyncio.Lock()

    async def mock_executor(step, context):
        nonlocal current_active
        async with lock:
            current_active += 1
            active_counts.append(current_active)
        await asyncio.sleep(0.1)
        async with lock:
            current_active -= 1
        return ToolResult(success=True, data=f"Result {step.step_id}")

    verifier = FastMockVerifier()
    start_t = time.time()
    res_ctx = await scheduler.execute_dag_plan(ctx, plan, verifier, mock_executor)
    elapsed = time.time() - start_t

    # All 3 ran in parallel, max concurrent active reached > 1, elapsed time < 0.28s
    assert max(active_counts) > 1
    assert elapsed < 0.28

@pytest.mark.asyncio
async def test_concurrency_limit_enforcement():
    await init_db()
    scheduler = DAGScheduler(max_concurrent=2)
    ctx = ExecutionContext(task_id="task_limit", goal="Limit test")
    plan = TaskPlan(
        goal="Limit test",
        steps=[
            PlanStepSchema(id="step_1", title="Job 1", tool="git_status", dependencies=[]),
            PlanStepSchema(id="step_2", title="Job 2", tool="list_directory", dependencies=[]),
            PlanStepSchema(id="step_3", title="Job 3", tool="search_files", dependencies=[]),
            PlanStepSchema(id="step_4", title="Job 4", tool="read_file", dependencies=[])
        ]
    )

    active_counts = []
    current_active = 0
    lock = asyncio.Lock()

    async def mock_executor(step, context):
        nonlocal current_active
        async with lock:
            current_active += 1
            active_counts.append(current_active)
        await asyncio.sleep(0.05)
        async with lock:
            current_active -= 1
        return ToolResult(success=True, data=f"Result {step.step_id}")

    verifier = FastMockVerifier()
    res_ctx = await scheduler.execute_dag_plan(ctx, plan, verifier, mock_executor)
    assert max(active_counts) <= 2
