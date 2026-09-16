import os
import pytest
import asyncio
import tempfile
import subprocess

from core.tools.git import (
    GitStatusTool, GitDiffTool, GitLogTool, GitBranchTool,
    detect_git_repository, parse_unified_diff
)
from core.filesystem.permission_manager import permission_manager

@pytest.mark.asyncio
async def test_git_repository_detection_and_tools():
    with tempfile.TemporaryDirectory() as tmp_dir:
        permission_manager.register_project_boundary("git-proj", tmp_dir)
        
        # Initialize a real Git repo in tmp_dir
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Cocoa Test"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@cocoa.local"], cwd=tmp_dir, check=True)

        # 1. Detect repository before any commit
        status_info = await detect_git_repository(tmp_dir)
        assert status_info["is_git_repo"] is True
        assert status_info["is_clean"] is True

        # Create a file
        test_file = os.path.join(tmp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def hello():\n    return 'world'\n")

        # 2. Status tool
        status_tool = GitStatusTool()
        res_status = await status_tool.execute({"working_directory": tmp_dir, "project_id": "git-proj"})
        assert res_status.success is True
        assert "test.py" in res_status.data["untracked_files"] or "test.py" in res_status.data["changed_files"]

        # Commit file
        subprocess.run(["git", "add", "test.py"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_dir, check=True)

        # 3. Log tool
        log_tool = GitLogTool()
        res_log = await log_tool.execute({"working_directory": tmp_dir, "project_id": "git-proj"})
        assert res_log.success is True
        assert len(res_log.data["commits"]) >= 1
        assert res_log.data["commits"][0]["message"] == "Initial commit"

        # Modify file to produce a diff
        with open(test_file, "a") as f:
            f.write("\ndef add(a, b):\n    return a + b\n")

        # 4. Diff tool
        diff_tool = GitDiffTool()
        res_diff = await diff_tool.execute({"working_directory": tmp_dir, "project_id": "git-proj"})
        assert res_diff.success is True
        assert res_diff.data["files_changed_count"] >= 1
        assert res_diff.data["total_additions"] > 0

        # 5. Branch tool
        branch_tool = GitBranchTool()
        res_branch = await branch_tool.execute({"working_directory": tmp_dir, "project_id": "git-proj"})
        assert res_branch.success is True
        assert res_branch.data["current_branch"] != ""

def test_parse_unified_diff():
    sample_diff = """diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("Updated")
     pass
"""
    parsed = parse_unified_diff(sample_diff)
    assert len(parsed) == 1
    assert parsed[0]["file"] == "main.py"
    assert parsed[0]["additions"] == 1
