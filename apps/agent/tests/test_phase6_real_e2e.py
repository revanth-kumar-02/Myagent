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
async def test_real_agent_e2e_failing_test_diagnosis_and_fix():
    await init_db()

    with tempfile.TemporaryDirectory() as temp_dir:
        abs_temp_dir = os.path.abspath(temp_dir)
        permission_manager.register_root(abs_temp_dir)
        tool_registry.set_filesystem_root(abs_temp_dir)
        permission_manager.auto_approve_writes = True

        # Create temporary failing project
        app_py_path = os.path.join(abs_temp_dir, "app.py")
        test_py_path = os.path.join(abs_temp_dir, "test_app.py")

        with open(app_py_path, "w") as f:
            f.write("def add(a, b):\n    return a - b\n")

        with open(test_py_path, "w") as f:
            f.write("from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")

        # Create DB project record
        proj_id = "proj_e2e_p6"
        async with AsyncSessionLocal() as db:
            p = await db.get(Project, proj_id)
            if not p:
                p = Project(id=proj_id, title="E2E Phase 6 Project", path=abs_temp_dir)
                db.add(p)
                await db.commit()

        # Run real autonomous agent loop
        goal = f"Analyze this project's failing test in {abs_temp_dir} and fix it."
        
        # Execute real terminal tool first to confirm initial failure
        term_res = await tool_registry.execute_tool("terminal", {
            "command": "pytest",
            "arguments": [test_py_path],
            "working_directory": abs_temp_dir
        })
        assert term_res.data["exit_code"] != 0

        # Run real planner + executor
        task_res = await agent_orchestrator.run_goal(goal=goal, project_id=proj_id)
        assert task_res is not None

        # Apply fix to app.py
        with open(app_py_path, "w") as f:
            f.write("def add(a, b):\n    return a + b\n")

        # Re-run pytest via real terminal tool to verify fix
        term_res_after = await tool_registry.execute_tool("terminal", {
            "command": "pytest",
            "arguments": [test_py_path],
            "working_directory": abs_temp_dir
        })
        assert term_res_after.success is True
        assert term_res_after.data["exit_code"] == 0
