import os
import pytest
import asyncio
import tempfile
import subprocess
from db.session import init_db, AsyncSessionLocal
from db.models import Task, Project
from core.agent import agent_orchestrator
from core.filesystem.permission_manager import permission_manager
from core.tools.registry import tool_registry

@pytest.mark.asyncio
async def test_unified_computer_orchestration_e2e():
    await init_db()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_id = "e2e-orchestration-proj"
        async with AsyncSessionLocal() as db:
            p = await db.get(Project, project_id)
            if not p:
                db.add(Project(id=project_id, title="E2E Proj", path=tmp_dir))
                await db.commit()

        permission_manager.register_project_boundary(project_id, tmp_dir)
        tool_registry.set_filesystem_root(tmp_dir)
        
        # 1. Setup mock workspace with git repository
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "E2E Tester"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "e2e@cocoa.local"], cwd=tmp_dir, check=True)

        # Create source and test file
        test_file = os.path.join(tmp_dir, "test_app.py")
        with open(test_file, "w") as f:
            f.write("def test_addition():\n    assert 1 + 1 == 2\n")

        subprocess.run(["git", "add", "test_app.py"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial test setup"], cwd=tmp_dir, check=True)

        # 2. Run agent with goal "Analyze this project's failing tests"
        goal = "Analyze this project's failing tests"
        
        # Override working directory for tools in current context
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            task_record = await agent_orchestrator.run_goal(goal, project_id=project_id)
            
            assert task_record is not None
            assert task_record.status in ("completed", "failed", "executing")
            assert task_record.title == goal

        finally:
            os.chdir(old_cwd)
