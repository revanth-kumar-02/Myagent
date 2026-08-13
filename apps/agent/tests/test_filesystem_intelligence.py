import os
import shutil
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from core.filesystem.path_validator import PathValidator, PathSecurityError
from core.filesystem.permission_manager import PermissionManager, PermissionLevel
from core.filesystem.tools import (
    FilesystemToolSet,
    ListDirectoryInput, SearchFilesInput, ReadFileInput, InspectFileInput,
    CreateFileInput, EditFileInput, MoveFileInput, DeleteFileInput
)
from core.tools.registry import ToolRegistry

@pytest.fixture
def temp_workspace():
    """Creates an isolated temporary directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cocoa_fs_test_")
    
    # Populate test structure
    workspace = Path(temp_dir)
    (workspace / "subfolder").mkdir()
    (workspace / "node_modules").mkdir()
    (workspace / ".git").mkdir()

    with open(workspace / "README.md", "w", encoding="utf-8") as f:
        f.write("# Test Workspace\nLine 2: Authentication logic here\nLine 3: End of file")

    with open(workspace / "subfolder" / "auth.py", "w", encoding="utf-8") as f:
        f.write("def login(username, password):\n    return True\n")

    # Binary file
    with open(workspace / "sample.bin", "wb") as f:
        f.write(b"\x00\x01\x02\x03\x04\x05BINARY_DATA")

    yield workspace

    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def filesystem_setup(temp_workspace):
    validator = PathValidator([temp_workspace])
    perm_manager = PermissionManager(auto_approve_writes=True)
    toolset = FilesystemToolSet(validator, perm_manager)
    return validator, perm_manager, toolset, temp_workspace

# ─── 1. Path Validator Security Tests ─────────────────────────────

def test_path_validator_security(temp_workspace):
    validator = PathValidator([temp_workspace])

    # Valid relative and absolute paths within root
    assert validator.validate_path("README.md") == temp_workspace / "README.md"
    assert validator.validate_path(str(temp_workspace / "subfolder" / "auth.py")) == temp_workspace / "subfolder" / "auth.py"

    # Reject path traversal ../
    with pytest.raises(PathSecurityError) as exc_info:
        validator.validate_path("../../etc/passwd")
    assert exc_info.value.code == "PATH_NOT_ALLOWED"

    # Reject /project/../../etc/passwd traversal
    with pytest.raises(PathSecurityError) as exc_info:
        validator.validate_path(str(temp_workspace / "../../etc/passwd"))
    assert exc_info.value.code == "PATH_NOT_ALLOWED"

    # Reject unauthorized absolute paths
    with pytest.raises(PathSecurityError) as exc_info:
        validator.validate_path("/etc/shadow")
    assert exc_info.value.code == "PATH_NOT_ALLOWED"

def test_symlink_escape_rejection(temp_workspace):
    validator = PathValidator([temp_workspace])
    outside_file = tempfile.NamedTemporaryFile(delete=False)
    outside_file.write(b"secret")
    outside_file.close()

    symlink_path = temp_workspace / "symlink_escape"
    try:
        os.symlink(outside_file.name, symlink_path)
        with pytest.raises(PathSecurityError) as exc_info:
            validator.validate_path("symlink_escape")
        assert exc_info.value.code in ["PATH_NOT_ALLOWED", "SYMLINK_ESCAPE"]
    finally:
        os.unlink(outside_file.name)
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()


# ─── 2. List Directory Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_list_directory(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup
    res = await toolset.list_directory(ListDirectoryInput(path="."))

    assert res["success"] is True
    entries = res["result"]["entries"]
    entry_names = [e["name"] for e in entries]

    # Verify noisy dirs are filtered out
    assert "node_modules" not in entry_names
    assert ".git" not in entry_names

    # Verify valid files and subfolders are returned
    assert "README.md" in entry_names
    assert "subfolder" in entry_names


# ─── 3. Search Files Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_files(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    # Filename search
    res = await toolset.search_files(SearchFilesInput(query="auth", search_type="filename"))
    assert res["success"] is True
    assert len(res["result"]["matches"]) == 1
    assert res["result"]["matches"][0]["path"] == "subfolder/auth.py"

    # Content search
    res_content = await toolset.search_files(SearchFilesInput(query="Authentication", search_type="content"))
    assert res_content["success"] is True
    assert len(res_content["result"]["matches"]) == 1
    assert res_content["result"]["matches"][0]["path"] == "README.md"


# ─── 4. Read File & Binary Rejection Tests ────────────────────────

@pytest.mark.asyncio
async def test_read_file(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    # Valid text read
    res = await toolset.read_file(ReadFileInput(path="README.md"))
    assert res["success"] is True
    assert "Test Workspace" in res["result"]["content"]
    assert res["result"]["total_lines"] == 3

    # Ranged read
    res_range = await toolset.read_file(ReadFileInput(path="README.md", start_line=2, end_line=2))
    assert res_range["success"] is True
    assert "Line 2: Authentication" in res_range["result"]["content"]

    # Reject binary file
    res_bin = await toolset.read_file(ReadFileInput(path="sample.bin"))
    assert res_bin["success"] is False
    assert res_bin["error"]["code"] == "BINARY_FILE"


# ─── 5. Inspect File Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_inspect_file(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    res = await toolset.inspect_file(InspectFileInput(path="README.md"))
    assert res["success"] is True
    assert res["result"]["name"] == "README.md"
    assert res["result"]["is_file"] is True
    assert res["result"]["size"] > 0


# ─── 6. Write Operations & Post-Write Verification Tests ───────────

@pytest.mark.asyncio
async def test_create_file(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    res = await toolset.create_file(CreateFileInput(path="notes.md", content="# Project Notes"))
    assert res["success"] is True
    assert res["result"]["verified"] is True
    assert (workspace / "notes.md").exists()
    assert (workspace / "notes.md").read_text() == "# Project Notes"

@pytest.mark.asyncio
async def test_edit_file(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    res = await toolset.edit_file(EditFileInput(
        path="README.md",
        target_content="# Test Workspace",
        replacement_content="# Updated Test Workspace"
    ))
    assert res["success"] is True
    assert res["result"]["verified"] is True
    assert "# Updated Test Workspace" in (workspace / "README.md").read_text()

@pytest.mark.asyncio
async def test_move_file(filesystem_setup):
    _, _, toolset, workspace = filesystem_setup

    res = await toolset.move_file(MoveFileInput(source_path="README.md", destination_path="subfolder/README_moved.md"))
    assert res["success"] is True
    assert res["result"]["verified"] is True
    assert not (workspace / "README.md").exists()
    assert (workspace / "subfolder" / "README_moved.md").exists()

@pytest.mark.asyncio
async def test_delete_file_approval(filesystem_setup):
    _, perm_manager, toolset, workspace = filesystem_setup

    # Mock permission prompt response to grant DELETE
    perm_manager.check_permission = AsyncMock(return_value=True)

    res = await toolset.delete_file(DeleteFileInput(path="sample.bin"))
    assert res["success"] is True
    assert res["result"]["verified"] is True
    assert not (workspace / "sample.bin").exists()


# ─── 7. Permission Denial Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_permission_denial(filesystem_setup):
    _, perm_manager, toolset, workspace = filesystem_setup

    # Force permission denial
    perm_manager.check_permission = AsyncMock(return_value=False)

    res = await toolset.create_file(CreateFileInput(path="forbidden.txt", content="test"))
    assert res["success"] is False
    assert res["error"]["code"] == "PERMISSION_DENIED"
    assert not (workspace / "forbidden.txt").exists()


# ─── 8. Tool Registry Integration Tests ───────────────────────────

@pytest.mark.asyncio
async def test_tool_registry_dispatch(filesystem_setup):
    validator, perm_manager, toolset, workspace = filesystem_setup
    registry = ToolRegistry()
    registry.set_filesystem_root(str(workspace))

    # Test list_directory via registry
    res = await registry.execute_tool("list_directory", {"path": "."})
    assert res.success is True
    assert "entries" in res.data
