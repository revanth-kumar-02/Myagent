import pytest
import asyncio
from sqlalchemy.future import select
from db.session import init_db, AsyncSessionLocal
from db.models import Automation
from core.scheduler_manager import automation_scheduler

@pytest.mark.asyncio
async def test_automation_lifecycle_and_scheduler_registration():
    await init_db()
    await automation_scheduler.start()

    try:
        # 1. Create active automation with short 1-second interval
        async with AsyncSessionLocal() as db:
            auto = Automation(
                title="Test Short Interval Automation",
                description="Perform a quick health verification task",
                trigger_type="schedule",
                trigger_config={"type": "interval", "seconds": 1},
                is_active=True
            )
            db.add(auto)
            await db.commit()
            await db.refresh(auto)
            auto_id = auto.id

        # 2. Register job in scheduler
        success = automation_scheduler.register_automation_job(auto)
        assert success is True
        assert automation_scheduler.scheduler.get_job(str(auto_id)) is not None

        # 3. Trigger job execution directly
        await automation_scheduler._execute_automation(auto_id)

        # 4. Verify DB updated with execution timestamp and result
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Automation).where(Automation.id == auto_id))
            updated_auto = result.scalar_one()
            assert updated_auto.last_run_at is not None
            assert updated_auto.last_run_result is not None

        # 5. Disable automation -> must unregister job
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Automation).where(Automation.id == auto_id))
            disabled_auto = result.scalar_one()
            disabled_auto.is_active = False
            await db.commit()

        automation_scheduler.remove_automation_job(auto_id)
        assert automation_scheduler.scheduler.get_job(str(auto_id)) is None

        # Clean up
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Automation).where(Automation.id == auto_id))
            auto_to_del = result.scalar_one_or_none()
            if auto_to_del:
                await db.delete(auto_to_del)
                await db.commit()

    finally:
        await automation_scheduler.stop()

@pytest.mark.asyncio
async def test_scheduler_recovery_on_startup():
    await init_db()

    # Create enabled automation in DB
    async with AsyncSessionLocal() as db:
        auto = Automation(
            title="Startup Recovery Test Job",
            description="Verify restoration on backend startup",
            trigger_type="schedule",
            trigger_config={"type": "interval", "seconds": 300},
            is_active=True
        )
        db.add(auto)
        await db.commit()
        await db.refresh(auto)
        auto_id = auto.id

    try:
        # Simulate backend startup recovery
        await automation_scheduler.start()

        # Job must be recovered and present in scheduler
        job = automation_scheduler.scheduler.get_job(str(auto_id))
        assert job is not None
        assert job.id == str(auto_id)

    finally:
        await automation_scheduler.stop()

        # Cleanup
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Automation).where(Automation.id == auto_id))
            auto_to_del = result.scalar_one_or_none()
            if auto_to_del:
                await db.delete(auto_to_del)
                await db.commit()

@pytest.mark.asyncio
async def test_failed_automation_does_not_crash_scheduler():
    await init_db()
    await automation_scheduler.start()

    try:
        # Execute bogus non-existent automation ID
        await automation_scheduler._execute_automation("invalid-bogus-automation-id")
        
        # Scheduler must remain running and alive
        assert automation_scheduler.scheduler.running is True
    finally:
        await automation_scheduler.stop()
