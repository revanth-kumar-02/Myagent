import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class GitInfo:
    def __init__(
        self,
        is_repo: bool,
        branch: str = "main",
        latest_commit_hash: Optional[str] = None,
        latest_commit_message: Optional[str] = None,
        latest_commit_author: Optional[str] = None,
        latest_commit_date: Optional[datetime] = None,
        modified_files_count: int = 0,
        status_clean: bool = True
    ):
        self.is_repo = is_repo
        self.branch = branch
        self.latest_commit_hash = latest_commit_hash
        self.latest_commit_message = latest_commit_message
        self.latest_commit_author = latest_commit_author
        self.latest_commit_date = latest_commit_date
        self.modified_files_count = modified_files_count
        self.status_clean = status_clean

def inspect_git_repository(project_path: str) -> GitInfo:
    """Extracts structured Git metadata for a project root directory using git commands."""
    path = Path(project_path)
    if not path.exists() or not (path / ".git").exists():
        return GitInfo(is_repo=False)

    try:
        # Branch
        branch_res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "main"

        # Latest commit info: hash|author|iso_date|subject
        commit_res = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%H|%an|%ad|%s", "--date=iso"],
            capture_output=True, text=True, timeout=5
        )
        hash_val = None
        author_val = None
        date_val = None
        msg_val = None

        if commit_res.returncode == 0 and commit_res.stdout.strip():
            parts = commit_res.stdout.strip().split("|", 3)
            if len(parts) >= 4:
                hash_val = parts[0]
                author_val = parts[1]
                try:
                    date_val = datetime.fromisoformat(parts[2].replace(" ", "T", 1).split()[0])
                except Exception:
                    date_val = datetime.utcnow()
                msg_val = parts[3]

        # Status / Modified files count
        status_res = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        modified_count = 0
        is_clean = True
        if status_res.returncode == 0:
            lines = [l for l in status_res.stdout.splitlines() if l.strip()]
            modified_count = len(lines)
            is_clean = (modified_count == 0)

        return GitInfo(
            is_repo=True,
            branch=branch,
            latest_commit_hash=hash_val,
            latest_commit_message=msg_val,
            latest_commit_author=author_val,
            latest_commit_date=date_val,
            modified_files_count=modified_count,
            status_clean=is_clean
        )
    except Exception:
        return GitInfo(is_repo=True, branch="main")
