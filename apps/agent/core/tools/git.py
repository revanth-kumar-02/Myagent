import os
import re
import shlex
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.filesystem.permission_manager import permission_manager, PermissionLevel, PermissionScope
from core.filesystem.path_validator import PathValidator
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

# ─── Helper Functions ──────────────────────────────────────────────────────

async def run_git_command(args: List[str], cwd: str, timeout_seconds: float = 15.0) -> Dict[str, Any]:
    """Helper to run a git subprocess command safely and return output."""
    norm_cwd = os.path.abspath(cwd)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=norm_cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e)
        }

async def detect_git_repository(working_dir: str) -> Dict[str, Any]:
    """Detects if working_dir is inside a git repository and extracts structured details."""
    norm_cwd = os.path.abspath(working_dir)
    res_root = await run_git_command(["rev-parse", "--show-toplevel"], norm_cwd)
    
    if not res_root["success"]:
        return {
            "is_git_repo": False,
            "repo_root": "",
            "current_branch": "",
            "is_clean": True,
            "changed_files": [],
            "staged_files": [],
            "untracked_files": []
        }

    repo_root = res_root["stdout"].strip()

    # Get current branch
    res_branch = await run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = res_branch["stdout"].strip() if res_branch["success"] else "HEAD"

    # Get status porcelain
    res_status = await run_git_command(["status", "--porcelain"], repo_root)
    lines = res_status["stdout"].splitlines() if res_status["success"] else []

    changed_files = []
    staged_files = []
    untracked_files = []

    for line in lines:
        if len(line) < 4:
            continue
        index_status = line[0]
        work_status = line[1]
        file_path = line[3:].strip()

        if index_status not in (" ", "?"):
            staged_files.append(file_path)
        if work_status not in (" ", "?"):
            changed_files.append(file_path)
        if index_status == "?" and work_status == "?":
            untracked_files.append(file_path)

    is_clean = len(lines) == 0

    return {
        "is_git_repo": True,
        "repo_root": repo_root,
        "current_branch": current_branch,
        "is_clean": is_clean,
        "changed_files": list(set(changed_files)),
        "staged_files": list(set(staged_files)),
        "untracked_files": list(set(untracked_files))
    }

def parse_unified_diff(diff_text: str) -> List[Dict[str, Any]]:
    """Parses unified diff output into structured file hunks with addition/deletion counts."""
    files_diff = []
    current_file = None
    additions = 0
    deletions = 0
    current_hunk = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                current_file["additions"] = additions
                current_file["deletions"] = deletions
                files_diff.append(current_file)
            
            parts = line.split()
            filename = parts[-1].lstrip("b/") if len(parts) >= 4 else "unknown"
            current_file = {
                "file": filename,
                "additions": 0,
                "deletions": 0,
                "hunks": []
            }
            additions = 0
            deletions = 0
        elif line.startswith("@@") and current_file:
            current_hunk = {"header": line, "lines": []}
            current_file["hunks"].append(current_hunk)
        elif current_hunk:
            current_hunk["lines"].append(line)
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

    if current_file:
        current_file["additions"] = additions
        current_file["deletions"] = deletions
        files_diff.append(current_file)

    return files_diff

# ─── Inputs ────────────────────────────────────────────────────────────────

class GitStatusInput(BaseModel):
    working_directory: Optional[str] = Field(default=None, description="Repository working directory")
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

class GitDiffInput(BaseModel):
    working_directory: Optional[str] = Field(default=None)
    staged: bool = Field(default=False, description="If True, inspect staged changes (--cached)")
    file_path: Optional[str] = Field(default=None, description="Optional target file path to diff")
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

class GitLogInput(BaseModel):
    working_directory: Optional[str] = Field(default=None)
    limit: int = Field(default=10, description="Max commit count to retrieve")
    file_path: Optional[str] = Field(default=None, description="Optional file path to filter log history")
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

class GitBranchInput(BaseModel):
    working_directory: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

class GitShowInput(BaseModel):
    commit_hash: str = Field(description="Target commit hash or reference (e.g. HEAD, HEAD~1, commit SHA)")
    working_directory: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

class GitRemoteInput(BaseModel):
    working_directory: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)

# ─── Tools ─────────────────────────────────────────────────────────────────

class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Inspects Git repository status, current branch, clean/dirty state, and modified/staged/untracked files."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitStatusInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation="git_status",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_status")

        status_info = await detect_git_repository(cwd)
        if not status_info["is_git_repo"]:
            return ToolResult(success=False, data=status_info, error="Directory is not a valid Git repository")

        return ToolResult(success=True, data=status_info, error="")


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Provides structured Git diff information (file, additions, deletions, hunks, change summary)."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitDiffInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation="git_diff",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_diff")

        git_args = ["diff"]
        if inp.staged:
            git_args.append("--cached")
        if inp.file_path:
            git_args.extend(["--", inp.file_path])

        res = await run_git_command(git_args, cwd)
        if not res["success"]:
            return ToolResult(success=False, error=f"Git diff failed: {res['stderr']}")

        parsed_diffs = parse_unified_diff(res["stdout"])
        total_additions = sum(f["additions"] for f in parsed_diffs)
        total_deletions = sum(f["deletions"] for f in parsed_diffs)

        summary = {
            "files_changed_count": len(parsed_diffs),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "staged": inp.staged,
            "diffs": parsed_diffs,
            "raw_diff": res["stdout"][:20000] # Truncate raw diff for safety
        }

        return ToolResult(success=True, data=summary, error="")


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Retrieves structured Git commit log history (commit_hash, author, date, message, files_changed)."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitLogInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation="git_log",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_log")

        # Format: hash|author|date|subject
        format_str = "%H|%an|%ad|%s"
        git_args = ["log", f"-n{inp.limit}", f"--format={format_str}", "--name-only"]
        if inp.file_path:
            git_args.extend(["--", inp.file_path])

        res = await run_git_command(git_args, cwd)
        if not res["success"]:
            return ToolResult(success=False, error=f"Git log failed: {res['stderr']}")

        commits = []
        raw_blocks = res["stdout"].strip().split("\n\n")
        
        for block in raw_blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            header_parts = lines[0].split("|")
            if len(header_parts) >= 4:
                commit_hash = header_parts[0]
                author = header_parts[1]
                date_str = header_parts[2]
                message = "|".join(header_parts[3:])
                files_changed = lines[1:] if len(lines) > 1 else []
                commits.append({
                    "commit_hash": commit_hash,
                    "author": author,
                    "date": date_str,
                    "message": message,
                    "files_changed": files_changed
                })

        return ToolResult(success=True, data={"commit_count": len(commits), "commits": commits}, error="")


class GitBranchTool(BaseTool):
    name = "git_branch"
    description = "Lists Git branches (current branch, local branches, remote branches)."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitBranchInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation="git_branch",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_branch")

        res = await run_git_command(["branch", "-a"], cwd)
        if not res["success"]:
            return ToolResult(success=False, error=f"Git branch failed: {res['stderr']}")

        branches = []
        current_branch = ""
        for line in res["stdout"].splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("*"):
                b_name = line_str[1:].strip()
                current_branch = b_name
                branches.append({"name": b_name, "current": True})
            else:
                branches.append({"name": line_str, "current": False})

        return ToolResult(success=True, data={"current_branch": current_branch, "branches": branches}, error="")


class GitShowTool(BaseTool):
    name = "git_show"
    description = "Inspects details and diffs of a specific Git commit."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitShowInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation=f"git_show {inp.commit_hash}",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_show")

        res = await run_git_command(["show", inp.commit_hash, "--stat"], cwd)
        if not res["success"]:
            return ToolResult(success=False, error=f"Git show failed: {res['stderr']}")

        return ToolResult(success=True, data={"commit_hash": inp.commit_hash, "details": res["stdout"][:10000]}, error="")


class GitRemoteTool(BaseTool):
    name = "git_remote"
    description = "Lists Git remote repository names and URLs."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        inp = GitRemoteInput(**params)
        cwd = inp.working_directory or os.getcwd()

        is_granted = await permission_manager.check_permission(
            tool_name=self.name,
            path=cwd,
            operation="git_remote",
            permission_level=PermissionLevel.GIT_READ,
            task_id=inp.task_id,
            project_id=inp.project_id
        )
        if not is_granted:
            return ToolResult(success=False, error="Permission denied for git_remote")

        res = await run_git_command(["remote", "-v"], cwd)
        if not res["success"]:
            return ToolResult(success=False, error=f"Git remote failed: {res['stderr']}")

        remotes = []
        for line in res["stdout"].splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                remotes.append({"name": parts[0], "url": parts[1], "type": parts[2] if len(parts) > 2 else ""})

        return ToolResult(success=True, data={"remotes": remotes}, error="")
