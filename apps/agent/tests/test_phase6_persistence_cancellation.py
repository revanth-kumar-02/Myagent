import pytest
import asyncio
import uuid
from core.dag_scheduler import DAGScheduler, dag_scheduler
from db.session import init_db, AsyncSessionLocal
from db.models import Task, TaskStep

@pytest.mark.asyncio
async def test_task_cancellation():
    scheduler = DAGScheduler()
    task_id = f"cancel_{uuid.uuid4()}"
    scheduler.cancel_task(task_id)
    assert scheduler.is_cancelled(task_id) is True

@pytest.mark.asyncio
async def test_interrupted_task_recovery():
    await init_db()
    test_task_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        t = Task(
            id=test_task_id,
            title="Interrupted Task",
            description="Task interrupted mid-run",
            status="executing"
        )
        db.add(t)
        await db.commit()

    # Trigger recovery scan
    await dag_scheduler.recover_interrupted_tasks()

    async with AsyncSessionLocal() as db:
        recovered_task = await db.get(Task, test_task_id)
        assert recovered_task.status == "pending"
