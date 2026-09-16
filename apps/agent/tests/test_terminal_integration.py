import os
import pytest
import asyncio
import tempfile
from db.session import init_db, AsyncSessionLocal
from db.models import Project
from core.tools.terminal import TerminalTool, ProcessExecutor
from core.filesystem.path_validator import PathValidator
from core.filesystem.permission_manager import permission_manager

@pytest.mark.asyncio
async def test_terminal_integration_safe_command():
    await init_db()
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_id = "proj-test-1"
        async with AsyncSessionLocal() as db:
            p = await db.get(Project, project_id)
            if not p:
                db.add(Project(id=project_id, title="Test Proj 1", path=tmp_dir))
                await db.commit()

        validator = PathValidator([tmp_dir])
        permission_manager.register_project_boundary(project_id, tmp_dir)
        tool = TerminalTool(validator)

        res = await tool.execute({
            "command": "echo",
            "arguments": ["Hello Cocoa Terminal"],
            "working_directory": tmp_dir,
            "project_id": project_id
        })

        assert res.success is True
        assert "Hello Cocoa Terminal" in res.data["stdout"]
        assert res.data["exit_code"] == 0

@pytest.mark.asyncio
async def test_terminal_integration_timeout():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = await ProcessExecutor.execute(
            command_str="sleep 5",
            working_dir=tmp_dir,
            timeout_seconds=0.5
        )
        assert res["success"] is False
        assert res["exit_code"] == -1
        assert "timed out" in res["stderr"]

@pytest.mark.asyncio
async def test_terminal_integration_nonzero_exit():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = await ProcessExecutor.execute(
            command_str="ls non_existent_file_xyz_123",
            working_dir=tmp_dir,
            timeout_seconds=5.0
        )
        assert res["success"] is False
        assert res["exit_code"] != 0

@pytest.mark.asyncio
async def test_terminal_integration_workspace_boundary_escape():
    await init_db()
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_id = "proj-test-2"
        async with AsyncSessionLocal() as db:
            p = await db.get(Project, project_id)
            if not p:
                db.add(Project(id=project_id, title="Test Proj 2", path=tmp_dir))
                await db.commit()

        validator = PathValidator([tmp_dir])
        tool = TerminalTool(validator)

        # Attempt to run command in unauthorized directory outside workspace
        res = await tool.execute({
            "command": "pwd",
            "working_directory": "/etc",
            "project_id": project_id
        })

        assert res.success is False
        assert "SECURITY BLOCKED" in res.error
