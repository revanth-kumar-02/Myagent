"""
tools.projects — Project and Workspace Discovery Tools (V8)

Tools:
  - ProjectsScanTool: Scans local workspace directories, discovers project folders,
    detects languages/frameworks/git status, and categorizes unfinished vs finished projects.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult

IGNORED_DIRS = {
    ".git", "node_modules", ".dart_tool", "build", "dist",
    "target", "__pycache__", ".venv", "venv", ".cache",
    ".idea", ".vscode", ".pytest_cache", ".gradle",
}

EXTENSION_MAP = {
    ".py": "Python", ".dart": "Dart", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".rs": "Rust", ".go": "Go",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".sql": "SQL", ".html": "HTML", ".css": "CSS",
    ".sh": "Shell", ".bash": "Bash", ".swift": "Swift",
    ".c": "C", ".cpp": "C++", ".h": "C/C++ Header",
}

DEFAULT_PROJECT_ROOTS = [
    "/home/rev/My_Personal_Space/Projects/Unfinished",
    "/home/rev/My_Personal_Space/Projects/Finished",
    "/home/rev/My_Personal_Space/Projects",
]


def _inspect_project_dir(project_path: Path) -> dict[str, Any] | None:
    """Inspects a directory to determine project metadata, framework, language, and git status."""
    if not project_path.is_dir():
        return None

    name = project_path.name
    top_level_files: list[str] = []
    top_level_folders: list[str] = []
    config_snippets: dict[str, str] = {}

    try:
        for entry in project_path.iterdir():
            if entry.is_dir():
                if not entry.name.startswith(".") and entry.name not in IGNORED_DIRS:
                    top_level_folders.append(entry.name)
            elif entry.is_file():
                top_level_files.append(entry.name)
                lower = entry.name.lower()
                if lower in ("pubspec.yaml", "package.json", "requirements.txt", "pyproject.toml", "cargo.toml"):
                    try:
                        config_snippets[lower] = entry.read_text(encoding="utf-8", errors="ignore")[:4000]
                    except Exception:
                        pass
    except Exception:
        pass

    total_files = 0
    total_folders = 0
    lang_counts: dict[str, int] = {}

    def _walk(curr: Path, depth: int) -> None:
        nonlocal total_files, total_folders
        if depth > 4:
            return
        try:
            for item in curr.iterdir():
                if item.is_dir():
                    if item.name.startswith(".") or item.name in IGNORED_DIRS:
                        continue
                    total_folders += 1
                    _walk(item, depth + 1)
                elif item.is_file():
                    total_files += 1
                    ext = item.suffix.lower()
                    lang = EXTENSION_MAP.get(ext)
                    if lang:
                        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        except Exception:
            pass

    _walk(project_path, 1)

    sorted_langs = sorted(lang_counts.keys(), key=lambda l: lang_counts[l], reverse=True)
    lower_files = {f.lower() for f in top_level_files}
    project_type = "Generic Project"
    frameworks: list[str] = []

    # If top-level files are sparse, check if there is a single child directory with the same name
    if not lower_files and top_level_folders:
        nested_dir = project_path / top_level_folders[0]
        if nested_dir.is_dir():
            try:
                for entry in nested_dir.iterdir():
                    if entry.is_file():
                        lower = entry.name.lower()
                        lower_files.add(lower)
                        if lower in ("pubspec.yaml", "package.json", "requirements.txt", "pyproject.toml"):
                            try:
                                config_snippets[lower] = entry.read_text(encoding="utf-8", errors="ignore")[:4000]
                            except Exception:
                                pass
            except Exception:
                pass

    if "pubspec.yaml" in lower_files:
        content = config_snippets.get("pubspec.yaml", "")
        if "flutter:" in content:
            project_type = "Flutter Application"
            frameworks.append("Flutter")
        else:
            project_type = "Dart Package"
        if "riverpod" in content:
            frameworks.append("Riverpod")
    elif "package.json" in lower_files:
        content = config_snippets.get("package.json", "")
        if '"next"' in content:
            project_type = "Next.js Project"
            frameworks.append("Next.js")
        elif '"react"' in content:
            project_type = "React Application"
            frameworks.append("React")
        elif '"vue"' in content:
            project_type = "Vue.js Application"
            frameworks.append("Vue")
        elif '"express"' in content:
            project_type = "Express.js Backend"
            frameworks.append("Express")
        else:
            project_type = "Node.js Project"
        if "tailwind" in content:
            frameworks.append("TailwindCSS")
        if "vite" in content:
            frameworks.append("Vite")
    elif "cargo.toml" in lower_files:
        project_type = "Rust / Cargo Project"
    elif "pyproject.toml" in lower_files or "requirements.txt" in lower_files:
        content = config_snippets.get("requirements.txt", "") + config_snippets.get("pyproject.toml", "")
        if "fastapi" in content:
            project_type = "FastAPI / Python"
            frameworks.append("FastAPI")
        elif "django" in content:
            project_type = "Django / Python"
            frameworks.append("Django")
        elif "flask" in content:
            project_type = "Flask / Python"
            frameworks.append("Flask")
        else:
            project_type = "Python Project"
    elif "build.gradle" in lower_files or "build.gradle.kts" in lower_files:
        project_type = "Gradle Project"
    elif "pom.xml" in lower_files:
        project_type = "Maven / Java Project"
    elif "index.html" in lower_files:
        project_type = "HTML / Web Project"
    elif sorted_langs:
        project_type = f"{sorted_langs[0]} Project"

    # Git status
    git_status = "Not a Git repository"
    git_dir = project_path / ".git"
    if git_dir.is_dir():
        git_status = "Git repository"
        head_file = git_dir / "HEAD"
        if head_file.is_file():
            try:
                head_content = head_file.read_text(encoding="utf-8").strip()
                if head_content.startswith("ref: refs/heads/"):
                    branch = head_content.replace("ref: refs/heads/", "")
                    git_status = f"Git repository ({branch})"
            except Exception:
                pass

    last_mod = ""
    try:
        mtime = datetime.fromtimestamp(project_path.stat().st_mtime, tz=timezone.utc)
        last_mod = mtime.strftime("%b %d, %Y")
    except Exception:
        pass

    return {
        "name": name,
        "path": str(project_path.resolve()),
        "project_type": project_type,
        "frameworks": frameworks,
        "languages": sorted_langs,
        "git_status": git_status,
        "file_count": total_files,
        "folder_count": total_folders,
        "last_modified": last_mod,
    }


class ProjectsScanTool(BaseTool):
    """Scan and inspect local projects, workspace directories, and git status."""

    @property
    def tool_id(self) -> str:
        return "projects_scan"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DEVELOPMENT

    @property
    def description(self) -> str:
        return (
            "Scan, inspect, and list local project directories, frameworks, languages, "
            "git statuses, and unfinished/finished projects."
        )

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional directory path to scan. Defaults to user's projects directory",
                },
                "category": {
                    "type": "string",
                    "enum": ["all", "unfinished", "finished"],
                    "description": "Filter by project category: 'unfinished', 'finished', or 'all'. Defaults to 'all'.",
                },
            },
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        path_arg = p.get("path") or p.get("workspace_path") or ""
        category_filter = (p.get("category") or "all").lower()

        unfinished_dir = Path("/home/rev/My_Personal_Space/Projects/Unfinished")
        finished_dir = Path("/home/rev/My_Personal_Space/Projects/Finished")

        unfinished_projects: list[dict[str, Any]] = []
        finished_projects: list[dict[str, Any]] = []
        custom_projects: list[dict[str, Any]] = []

        # If a specific custom path is given
        if path_arg and path_arg not in (".", "workspace", "projects", "dictoraries", "directories"):
            resolved = Path(os.path.expanduser(str(path_arg).strip())).resolve()
            if not resolved.exists() or not resolved.is_dir():
                return self._make_result(error=f"Directory does not exist: {resolved}")

            # If scanning a specific project directly
            inspected = _inspect_project_dir(resolved)
            # If resolved is a parent folder containing projects
            for child in resolved.iterdir():
                if child.is_dir() and not child.name.startswith(".") and child.name not in IGNORED_DIRS:
                    sub_info = _inspect_project_dir(child)
                    if sub_info:
                        custom_projects.append(sub_info)

            if not custom_projects and inspected:
                custom_projects.append(inspected)

            summary = f"Scanned {len(custom_projects)} projects in {resolved}."
            return self._make_result(
                output={
                    "scanned_path": str(resolved),
                    "projects": custom_projects,
                    "count": len(custom_projects),
                    "summary": summary,
                }
            )

        # Default multi-directory scan: inspect Unfinished and Finished project roots
        if category_filter in ("all", "unfinished") and unfinished_dir.exists():
            for child in sorted(unfinished_dir.iterdir(), key=lambda x: x.name.lower()):
                if child.is_dir() and not child.name.startswith(".") and child.name not in IGNORED_DIRS:
                    info = _inspect_project_dir(child)
                    if info:
                        info["category"] = "Unfinished"
                        unfinished_projects.append(info)

        if category_filter in ("all", "finished") and finished_dir.exists():
            for child in sorted(finished_dir.iterdir(), key=lambda x: x.name.lower()):
                if child.is_dir() and not child.name.startswith(".") and child.name not in IGNORED_DIRS:
                    info = _inspect_project_dir(child)
                    if info:
                        info["category"] = "Finished"
                        finished_projects.append(info)

        total = len(unfinished_projects) + len(finished_projects)
        unfin_names = [p["name"] for p in unfinished_projects]
        fin_names = [p["name"] for p in finished_projects]

        summary_parts = []
        if unfinished_projects:
            summary_parts.append(
                f"{len(unfinished_projects)} unfinished projects in {unfinished_dir}: {', '.join(unfin_names)}"
            )
        if finished_projects:
            summary_parts.append(
                f"{len(finished_projects)} finished projects in {finished_dir}: {', '.join(fin_names)}"
            )

        summary = "Found " + "; ".join(summary_parts) if summary_parts else "No projects discovered."

        return self._make_result(
            output={
                "unfinished_projects": unfinished_projects,
                "finished_projects": finished_projects,
                "unfinished_count": len(unfinished_projects),
                "finished_count": len(finished_projects),
                "total_count": total,
                "summary": summary,
            }
        )
