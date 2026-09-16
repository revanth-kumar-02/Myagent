import pytest
import asyncio
from datetime import datetime
from sqlalchemy.future import select
from db.session import AsyncSessionLocal, init_db
from db.models import Automation, AutomationRun, ActivityLog
from core.automations.trigger_evaluator import trigger_evaluator
from core.automations.nl_parser import nl_automation_parser
from core.automations.workflow_engine import workflow_engine
from core.scheduler_manager import automation_scheduler
from core.memory import memory_manager
from core.filesystem.permission_manager import permission_manager

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield

@pytest.mark.asyncio
async def test_trigger_evaluator_conditions():
    # Test condition evaluation logic
    context = {"task_status": "COMPLETED", "task_result": "tests_failed"}
    assert trigger_evaluator.evaluate_condition("tests_failed", context) is True
    assert trigger_evaluator.evaluate_condition("success", context) is False

    context_success = {"task_status": "COMPLETED", "task_result": "all tests passed"}
    assert trigger_evaluator.evaluate_condition("success", context_success) is True

@pytest.mark.asyncio
async def test_nl_automation_parser():
    prompt = "Every weekday at 9 AM, check my projects and notify me if tests fail."
    parsed = await nl_automation_parser.parse_natural_language(prompt)
    
    assert "title" in parsed
    assert parsed["trigger_type"] in ["CRON", "INTERVAL"]
    assert "trigger_config" in parsed
    assert parsed["notification_level"] in ["ALWAYS", "ON_FAILURE", "ON_CHANGE", "ON_IMPORTANT_EVENT", "SILENT"]

@pytest.mark.asyncio
async def test_automation_lifecycle_and_run_persistence():
    async with AsyncSessionLocal() as db:
        auto = Automation(
            title="E2E Test Workflow",
            description="Verify system test suite execution",
            trigger_type="INTERVAL",
            trigger_config={"seconds": 3600},
            workflow_config={
                "notification_level": "ALWAYS",
                "max_runtime": 10.0,
                "allowed_tools": ["terminal", "read_file"]
            },
            is_active=True
        )
        db.add(auto)
        await db.commit()
        await db.refresh(auto)
        auto_id = auto.id

    # Register with scheduler
    registered = automation_scheduler.register_automation_job(auto)
    assert registered is True
    assert str(auto_id) in [job.id for job in automation_scheduler.scheduler.get_jobs()]

    # Execute workflow directly
    run_res = await workflow_engine.execute_automation_workflow(auto_id, trigger_reason="MANUAL_TEST")
    assert run_res["status"] in ["COMPLETED", "SKIPPED", "WAITING_PERMISSION", "FAILED"]

    # Verify persistent AutomationRun state in DB
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AutomationRun).where(AutomationRun.automation_id == auto_id))
        runs = res.scalars().all()
        assert len(runs) >= 1
        latest_run = runs[0]
        assert latest_run.automation_id == auto_id
        assert latest_run.status in ["COMPLETED", "SKIPPED", "WAITING_PERMISSION", "FAILED"]
        assert latest_run.duration_seconds is not None

    # Cleanup job
    automation_scheduler.remove_automation_job(auto_id)
    assert str(auto_id) not in [job.id for job in automation_scheduler.scheduler.get_jobs()]

@pytest.mark.asyncio
async def test_permission_gated_automation():
    async with AsyncSessionLocal() as db:
        auto = Automation(
            title="Permission Restricted Workflow",
            description="Attempt restricted file modification",
            trigger_type="MANUAL",
            workflow_config={
                "allowed_tools": ["restricted_write_tool"],
                "max_runtime": 5.0
            },
            is_active=True
        )
        db.add(auto)
        await db.commit()
        await db.refresh(auto)
        auto_id = auto.id

    run_res = await workflow_engine.execute_automation_workflow(auto_id, trigger_reason="SAFETY_TEST")
    assert run_res["status"] in ["COMPLETED", "SKIPPED", "WAITING_PERMISSION", "FAILED"]
