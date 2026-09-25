"""
api.http — HTTP endpoints for Kora Agent

REST is used for:
  - Health checks & system status
  - Model registry information (capabilities & metadata; no secrets)
  - Project management (CRUD)
  - Memory exploration & management
  - External DuckDuckGo research queries
  - Background task queries
  - Observability & Activity feeds
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.deps import get_model_registry, get_research_router, get_tool_registry
from models.registry import ModelRegistry
from research.router import ResearchRouter
from tools.registry import ToolRegistry

router = APIRouter(prefix="/api")

# In-memory stores for runtime desktop state
_projects_store: dict[str, dict[str, Any]] = {}
_memory_store: list[dict[str, Any]] = []
_tasks_store: list[dict[str, Any]] = []
_activity_store: list[dict[str, Any]] = []


# ── Schemas ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    models_available: int = 0


class DatabaseHealthResponse(BaseModel):
    postgres: str  # CONNECTED / DISCONNECTED
    connection_pool: str  # READY / NOT READY
    schema_status: str  # VALID / INVALID
    pgvector: str  # AVAILABLE / UNAVAILABLE
    memory_persistence: str  # PASS / FAIL
    knowledge_graph_persistence: str  # PASS / FAIL
    rag_persistence: str  # PASS / FAIL
    postgres_version: str | None = None
    pgvector_version: str | None = None
    database_name: str | None = None
    host: str | None = None
    port: int | None = None


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""
    root_path: str = ""


class FsProjectCreateRequest(BaseModel):
    workspace_path: str
    name: str
    template: str | None = None


class FsLaunchRequest(BaseModel):
    target_path: str
    action: str = "vscode"


class MemoryCreateRequest(BaseModel):
    content: str
    type: str = "user_preference"
    confidence: float = 1.0
    importance: float = 0.5
    project_id: str | None = None
    source: str = "user_explicit"


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    type: str | None = None
    confidence: float | None = None
    importance: float | None = None
    status: str | None = None


class ResearchRequest(BaseModel):
    query: str
    max_results: int = 5


class AutomationCreateRequest(BaseModel):
    name: str
    description: str = ""
    goal: str
    trigger_type: str = "manual"
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    allowed_tools: list[str] = Field(default_factory=list)
    permission_scope: dict[str, Any] = Field(default_factory=dict)
    condition_logic: dict[str, Any] | None = None
    project_id: str | None = None


class AutomationUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    goal: str | None = None
    trigger_type: str | None = None
    trigger_config: dict[str, Any] | None = None
    priority: str | None = None
    allowed_tools: list[str] | None = None
    permission_scope: dict[str, Any] | None = None
    condition_logic: dict[str, Any] | None = None


class AutomationInterpretRequest(BaseModel):
    prompt: str
    project_id: str | None = None


# ── Health ──────────────────────────────────────────────────────────────────

_start_time = time.time()

@router.get("/health", response_model=HealthResponse)
async def health(registry: ModelRegistry = Depends(get_model_registry)) -> HealthResponse:
    """Liveness & readiness check."""
    num_models = len(list(registry.all()))
    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        models_available=num_models,
    )


@router.get("/health/db", response_model=DatabaseHealthResponse)
async def health_db() -> DatabaseHealthResponse:
    """
    Comprehensive infrastructure & persistence health check for PostgreSQL and pgvector.
    Strictly masks all credentials.
    """
    from db.client import AsyncSessionFactory, engine
    from db.schema import AgentMemory, Chunk, GraphEntity, Project
    from sqlalchemy import text

    postgres_status = "DISCONNECTED"
    pool_status = "NOT READY"
    schema_status = "INVALID"
    pgvector_status = "UNAVAILABLE"
    memory_status = "FAIL"
    kg_status = "FAIL"
    rag_status = "FAIL"
    pg_version: str | None = None
    vec_version: str | None = None

    db_url = engine.url
    db_name = db_url.database
    host = db_url.host
    port = db_url.port

    try:
        async with AsyncSessionFactory() as session:
            # 1. Connection & Version
            v_res = await session.execute(text("SELECT version();"))
            pg_version = str(v_res.scalar())
            postgres_status = "CONNECTED"
            pool_status = "READY"

            # 2. Extension check
            ext_res = await session.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            )
            ext_row = ext_res.fetchone()
            if ext_row:
                pgvector_status = "AVAILABLE"
                vec_version = str(ext_row[1])

            # 3. Schema tables check
            tbl_res = await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
                )
            )
            tables = {r[0] for r in tbl_res.fetchall()}
            required_tables = {"projects", "indexed_files", "chunks", "agent_memory", "graph_entities", "graph_relationships"}
            if required_tables.issubset(tables):
                schema_status = "VALID"

            # 4. Memory persistence verify
            mem_res = await session.execute(text("SELECT count(*) FROM agent_memory;"))
            if mem_res.scalar() is not None:
                memory_status = "PASS"

            # 5. Knowledge Graph persistence verify
            kg_res = await session.execute(text("SELECT count(*) FROM graph_entities;"))
            if kg_res.scalar() is not None:
                kg_status = "PASS"

            # 6. RAG persistence verify
            rag_res = await session.execute(text("SELECT count(*) FROM chunks;"))
            if rag_res.scalar() is not None:
                rag_status = "PASS"

    except Exception:
        pass

    return DatabaseHealthResponse(
        postgres=postgres_status,
        connection_pool=pool_status,
        schema_status=schema_status,
        pgvector=pgvector_status,
        memory_persistence=memory_status,
        knowledge_graph_persistence=kg_status,
        rag_persistence=rag_status,
        postgres_version=pg_version,
        pgvector_version=vec_version,
        database_name=db_name,
        host=host,
        port=port,
    )


@router.get("/health/providers")
async def health_providers() -> dict[str, Any]:
    """
    Returns live provider status, online/offline detection, and HuggingFace/Ollama health.
    """
    from api.deps import get_failover_manager
    fm = get_failover_manager()
    await fm.update_all_health()
    return fm.get_status_payload()


# ── Model Registry ──────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(registry: ModelRegistry = Depends(get_model_registry)) -> dict[str, Any]:
    """
    Return all registered models and their capabilities.
    Strictly excludes all API tokens or sensitive headers.
    """
    models_data = []
    for cfg in registry.all():
        models_data.append({
            "name": cfg.name,
            "provider": cfg.provider,
            "capabilities": cfg.capabilities,
            "context_window": cfg.context_window,
            "dimension": cfg.dimension,
        })
    return {"models": models_data}


# ── Projects ────────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects() -> dict[str, Any]:
    """List all workspace projects."""
    return {"projects": list(_projects_store.values())}


# ── Filesystem Project Endpoints ─────────────────────────────────────────────

IGNORED_DIRS = {
    '.git', 'node_modules', '.dart_tool', 'build', 'dist', 'target',
    '__pycache__', '.venv', 'venv', '.cache', '.idea', '.vscode',
    '.pytest_cache', '.gradle', 'obj', 'bin', '.next', '.turbo', 'coverage'
}

EXTENSION_MAP = {
    '.py': 'Python', '.pyw': 'Python', '.ipynb': 'Python (Jupyter)',
    '.dart': 'Dart',
    '.ts': 'TypeScript', '.tsx': 'TypeScript (React)',
    '.js': 'JavaScript', '.jsx': 'JavaScript (React)',
    '.mjs': 'JavaScript', '.cjs': 'JavaScript',
    '.rs': 'Rust', '.go': 'Go', '.c': 'C', '.h': 'C/C++ Header',
    '.cpp': 'C++', '.hpp': 'C++', '.cc': 'C++', '.cxx': 'C++',
    '.java': 'Java', '.kt': 'Kotlin', '.kts': 'Kotlin',
    '.sql': 'SQL', '.html': 'HTML', '.css': 'CSS',
    '.sh': 'Shell', '.bash': 'Bash', '.swift': 'Swift',
}


def _inspect_fs_project(project_dir: str, workspace_path: str) -> dict[str, Any] | None:
    if not os.path.isdir(project_dir):
        return None
    name = os.path.basename(project_dir)
    rel_path = os.path.relpath(project_dir, workspace_path)

    top_level_folders = []
    top_level_files = []
    config_snippets = {}

    try:
        with os.scandir(project_dir) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    if not entry.name.startswith('.') and entry.name not in IGNORED_DIRS:
                        top_level_folders.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    top_level_files.append(entry.name)
                    lower = entry.name.lower()
                    if lower in ('pubspec.yaml', 'package.json', 'requirements.txt', 'pyproject.toml'):
                        try:
                            with open(entry.path, 'r', encoding='utf-8', errors='ignore') as f:
                                config_snippets[lower] = f.read(4000)
                        except Exception:
                            pass
    except Exception:
        pass

    total_files = 0
    total_folders = 0
    lang_counts: dict[str, int] = {}

    def walk_bounded(current_dir: str, depth: int):
        nonlocal total_files, total_folders
        if depth > 4:
            return
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.startswith('.') or entry.name in IGNORED_DIRS:
                            continue
                        total_folders += 1
                        walk_bounded(entry.path, depth + 1)
                    elif entry.is_file(follow_symlinks=False):
                        total_files += 1
                        _, ext = os.path.splitext(entry.name)
                        lang = EXTENSION_MAP.get(ext.lower())
                        if lang:
                            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        except Exception:
            pass

    walk_bounded(project_dir, 1)

    sorted_langs = sorted(lang_counts.keys(), key=lambda l: lang_counts[l], reverse=True)

    lower_files = set(f.lower() for f in top_level_files)
    project_type = "Generic Project"
    frameworks = []

    if 'pubspec.yaml' in lower_files:
        content = config_snippets.get('pubspec.yaml', '')
        if 'flutter:' in content:
            project_type = "Flutter Application"
            frameworks.append("Flutter")
        else:
            project_type = "Dart Package"
        if 'riverpod' in content:
            frameworks.append("Riverpod")
    elif 'package.json' in lower_files:
        content = config_snippets.get('package.json', '')
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
        if 'tailwind' in content:
            frameworks.append("TailwindCSS")
        if 'vite' in content:
            frameworks.append("Vite")
    elif 'cargo.toml' in lower_files:
        project_type = "Rust / Cargo Project"
    elif 'pyproject.toml' in lower_files or 'requirements.txt' in lower_files:
        content = config_snippets.get('requirements.txt', '') + config_snippets.get('pyproject.toml', '')
        if 'fastapi' in content:
            project_type = "FastAPI / Python"
            frameworks.append("FastAPI")
        elif 'django' in content:
            project_type = "Django / Python"
            frameworks.append("Django")
        elif 'flask' in content:
            project_type = "Flask / Python"
            frameworks.append("Flask")
        else:
            project_type = "Python Project"
    elif 'pom.xml' in lower_files:
        project_type = "Maven / Java Project"
    elif 'build.gradle' in lower_files or 'build.gradle.kts' in lower_files:
        project_type = "Gradle Project"
    elif 'go.mod' in lower_files:
        project_type = "Go Module"
    elif 'cmakelists.txt' in lower_files:
        project_type = "CMake / C++ Project"
    elif sorted_langs:
        project_type = f"{sorted_langs[0]} Project"

    git_status = "Not a Git repository"
    git_dir = os.path.join(project_dir, ".git")
    if os.path.isdir(git_dir):
        git_status = "Git repository"
        head_path = os.path.join(git_dir, "HEAD")
        if os.path.isfile(head_path):
            try:
                with open(head_path, "r", encoding="utf-8") as f:
                    head_content = f.read().strip()
                if head_content.startswith("ref: refs/heads/"):
                    branch = head_content.replace("ref: refs/heads/", "")
                    git_status = f"Git repository ({branch})"
            except Exception:
                pass

    last_mod = ""
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(project_dir), tz=timezone.utc)
        last_mod = mtime.strftime("%b %d, %Y")
    except Exception:
        pass

    return {
        "id": project_dir,
        "name": name,
        "description": "",
        "root_path": project_dir,
        "relative_path": rel_path,
        "exists": True,
        "is_directory": True,
        "file_count": total_files,
        "folder_count": total_folders,
        "detected_languages": sorted_langs,
        "top_level_folders": top_level_folders,
        "git_status": git_status,
        "last_modified": last_mod,
        "project_type": project_type,
        "frameworks": frameworks,
        "chunk_count": 0,
        "created_at": last_mod,
    }


@router.get("/projects/fs/scan")
async def scan_fs_projects(workspace_path: str) -> dict[str, Any]:
    """Scan real child directories within workspace_path."""
    clean_path = os.path.expanduser(workspace_path.strip())
    if not os.path.isdir(clean_path):
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {clean_path}")

    projects = []
    try:
        with os.scandir(clean_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.startswith('.') or entry.name in IGNORED_DIRS:
                        continue
                    p_info = _inspect_fs_project(entry.path, clean_path)
                    if p_info:
                        projects.append(p_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan workspace: {e}")

    projects.sort(key=lambda p: p["name"].lower())
    return {"workspace_path": clean_path, "projects": projects}


@router.post("/projects/fs/create")
async def create_fs_project(req: FsProjectCreateRequest) -> dict[str, Any]:
    """Create a real directory on the filesystem."""
    clean_name = req.name.strip()
    if not clean_name or '/' in clean_name or '\\' in clean_name or '..' in clean_name:
        raise HTTPException(status_code=400, detail="Invalid project name (traversal not allowed)")

    workspace = os.path.expanduser(req.workspace_path.strip())
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=400, detail=f"Workspace does not exist: {workspace}")

    target_dir = os.path.join(workspace, clean_name)
    if os.path.exists(target_dir):
        raise HTTPException(status_code=400, detail=f"Directory already exists: {target_dir}")

    try:
        os.makedirs(target_dir, exist_ok=False)
        readme_path = os.path.join(target_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {clean_name}\n\nCreated with Kora Workspace.\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")

    p_info = _inspect_fs_project(target_dir, workspace)
    if not p_info:
        raise HTTPException(status_code=500, detail="Failed to inspect newly created project")
    return p_info


@router.post("/projects/fs/launch")
async def launch_fs_project(req: FsLaunchRequest) -> dict[str, Any]:
    """Open a project in VS Code or OS File Explorer."""
    path = os.path.expanduser(req.target_path.strip())
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Target path does not exist")

    sys_name = platform.system()
    action = req.action.lower()

    try:
        if action == "vscode":
            subprocess.Popen(["code", path])
            return {"status": "ok", "action": "vscode", "path": path}
        elif action == "explorer":
            if sys_name == "Linux":
                subprocess.Popen(["xdg-open", path])
            elif sys_name == "Darwin":
                subprocess.Popen(["open", path])
            elif sys_name == "Windows":
                subprocess.Popen(["explorer.exe", path])
            return {"status": "ok", "action": "explorer", "path": path}
        elif action == "terminal":
            if sys_name == "Linux":
                subprocess.Popen(["x-terminal-emulator", f"--working-directory={path}"])
            elif sys_name == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal", path])
            return {"status": "ok", "action": "terminal", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch {action}: {e}")

    return {"status": "unknown_action"}


@router.get("/projects/fs/tree")
async def get_fs_tree(project_path: str, sub_path: str = "") -> dict[str, Any]:
    """Fetch shallow directory tree."""
    clean_proj = os.path.expanduser(project_path.strip())
    target = os.path.join(clean_proj, sub_path.strip("/")) if sub_path else clean_proj
    if not os.path.isdir(target):
        return {"entries": []}

    entries = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                if entry.name.startswith('.') or entry.name in IGNORED_DIRS:
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
                size = 0
                if not is_dir and entry.is_file(follow_symlinks=False):
                    try:
                        size = entry.stat().st_size
                    except Exception:
                        pass
                entries.append({
                    "name": entry.name,
                    "relative_path": os.path.relpath(entry.path, clean_proj),
                    "absolute_path": entry.path,
                    "is_directory": is_dir,
                    "size_bytes": size,
                })
    except Exception:
        pass

    entries.sort(key=lambda e: (not e["is_directory"], e["name"].lower()))
    return {"entries": entries}


def _resolve_safe_fs_path(project_path: str, relative_path: str) -> str:
    """Resolve and enforce that relative_path resides strictly within project_path."""
    clean_proj = os.path.realpath(os.path.expanduser(project_path.strip()))
    if not os.path.isdir(clean_proj):
        raise HTTPException(status_code=400, detail=f"Project root does not exist: {clean_proj}")

    clean_rel = relative_path.strip().lstrip("/\\")
    full_path = os.path.realpath(os.path.join(clean_proj, clean_rel))

    # Reject path traversal or symlink escape
    if not (full_path.startswith(clean_proj + os.sep) or full_path == clean_proj):
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {clean_rel}")

    return full_path


@router.get("/projects/fs/file")
async def get_fs_file(project_path: str, path: str) -> dict[str, Any]:
    """Read a real project file for preview with strict traversal security."""
    full_path = _resolve_safe_fs_path(project_path, path)
    if os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="Cannot preview a directory as a file")

    ext = os.path.splitext(full_path)[1].lower()
    base_name = os.path.basename(full_path)
    size = os.path.getsize(full_path)
    mime_type, _ = mimetypes.guess_type(full_path)

    # Categories
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico", ".svg"}
    pdf_exts = {".pdf"}
    text_exts = {
        ".py", ".dart", ".js", ".ts", ".tsx", ".jsx", ".rs", ".java", ".kt", ".kts",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".css", ".scss", ".sass", ".less",
        ".html", ".htm", ".xml", ".json", ".yaml", ".yml", ".toml", ".md", ".markdown",
        ".sql", ".sh", ".bash", ".zsh", ".txt", ".text", ".env", ".gitignore",
        ".gitattributes", ".dockerignore", ".ini", ".cfg", ".conf", ".gradle",
        ".properties", ".csv", ".tsv", ".log", ".lock"
    }

    category = "binary"
    if ext in image_exts:
        category = "image"
        if not mime_type:
            mime_type = "image/svg+xml" if ext == ".svg" else f"image/{ext.lstrip('.')}"
    elif ext in pdf_exts:
        category = "pdf"
        mime_type = "application/pdf"
    elif ext in text_exts or base_name in {"Dockerfile", "Makefile", "CMakeLists.txt", "LICENSE", "Procfile"}:
        category = "text"
    else:
        # Check first 1024 bytes for null character
        try:
            with open(full_path, "rb") as f:
                chunk = f.read(1024)
                if b"\x00" not in chunk:
                    category = "text"
        except Exception:
            category = "binary"

    content = None
    truncated = False
    line_count = 0

    if category == "text":
        max_bytes = 2 * 1024 * 1024  # 2 MB limit for preview
        try:
            with open(full_path, "rb") as f:
                raw = f.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    truncated = True
                    raw = raw[:max_bytes]
                content = raw.decode("utf-8", errors="replace")
                line_count = content.count("\n") + 1
        except Exception as e:
            content = f"Error reading file: {e}"

    clean_proj = os.path.realpath(os.path.expanduser(project_path.strip()))
    rel_path = os.path.relpath(full_path, clean_proj)

    return {
        "name": base_name,
        "relative_path": rel_path,
        "absolute_path": full_path,
        "extension": ext,
        "category": category,
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": size,
        "content": content,
        "truncated": truncated,
        "line_count": line_count,
    }


@router.get("/projects/fs/file/raw")
async def get_fs_file_raw(project_path: str, path: str) -> FileResponse:
    """Stream raw file content (images, binaries) with traversal validation."""
    full_path = _resolve_safe_fs_path(project_path, path)
    if os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="Cannot stream a directory")
    mime_type, _ = mimetypes.guess_type(full_path)
    ext = os.path.splitext(full_path)[1].lower()
    if ext == ".svg" and not mime_type:
        mime_type = "image/svg+xml"
    return FileResponse(full_path, media_type=mime_type or "application/octet-stream")


@router.post("/projects")
async def create_project(req: ProjectCreateRequest) -> dict[str, Any]:
    """Create a new project."""
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": req.name,
        "description": req.description,
        "root_path": req.root_path or f"/workspace/{req.name.lower().replace(' ', '_')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 0,
        "chunk_count": 0,
    }
    _projects_store[project_id] = project
    return project


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    """Get project details."""
    if project_id not in _projects_store:
        raise HTTPException(status_code=404, detail="Project not found")
    return _projects_store[project_id]


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    """Delete a project."""
    if project_id in _projects_store:
        del _projects_store[project_id]
        return {"deleted": True, "project_id": project_id}
    raise HTTPException(status_code=404, detail="Project not found")


# ── Kora Automation Center ──────────────────────────────────────────────────

AUTOMATION_TEMPLATES = [
    {
        "id": "tpl_daily_ai_research",
        "category": "RESEARCH",
        "name": "Daily AI Research Brief",
        "description": "Performs automated web research every morning via DuckDuckGo and compiles key developments.",
        "goal": "Search the web for the latest artificial intelligence breakthroughs, open-source model releases, and framework updates, and synthesize a concise briefing.",
        "trigger_type": "cron",
        "trigger_config": {"cron_expr": "0 8 * * *", "schedule_label": "Every day at 08:00 AM"},
        "allowed_tools": ["web_search"],
        "planned_actions": [
            "Execute DuckDuckGo research query for top AI releases",
            "Extract snippets and citations from leading sources",
            "Synthesize structured daily brief with links",
            "Store findings in execution log",
        ],
    },
    {
        "id": "tpl_git_repo_watch",
        "category": "PROJECT",
        "name": "Monitor Git Changes",
        "description": "Periodically inspects local Git status and recent commits to report meaningful codebase changes.",
        "goal": "Inspect the Git repository for modified files, uncommitted changes, and recent commit history to produce a project change summary.",
        "trigger_type": "interval",
        "trigger_config": {"interval_seconds": 7200, "schedule_label": "Every 2 hours"},
        "allowed_tools": ["git_ops"],
        "planned_actions": [
            "Check Git working directory status and branch state",
            "Inspect recent commits in current branch",
            "Identify modified, staged, and untracked files",
            "Generate codebase change report",
        ],
    },
    {
        "id": "tpl_watch_project_dir",
        "category": "FILES",
        "name": "Watch Project Directory",
        "description": "Monitors project workspace directory for structure alterations and newly created files.",
        "goal": "Scan project directory tree, list top-level files, and verify integrity of project files.",
        "trigger_type": "interval",
        "trigger_config": {"interval_seconds": 3600, "schedule_label": "Every 1 hour"},
        "allowed_tools": ["directory_ops", "file_read"],
        "planned_actions": [
            "List project directory contents",
            "Verify file tree and detect changes",
            "Generate directory health report",
        ],
    },
    {
        "id": "tpl_system_health_check",
        "category": "SYSTEM",
        "name": "Daily System Health Check",
        "description": "Monitors CPU, memory, and disk space to ensure host system performance and stability.",
        "goal": "Query hardware metrics, verify free disk storage, memory headroom, and CPU usage.",
        "trigger_type": "cron",
        "trigger_config": {"cron_expr": "0 9 * * *", "schedule_label": "Every day at 09:00 AM"},
        "allowed_tools": ["system_info"],
        "planned_actions": [
            "Query CPU, memory, and disk usage metrics",
            "Evaluate thresholds for high utilization",
            "Generate system health audit report",
        ],
    },
    {
        "id": "tpl_weekly_dev_report",
        "category": "REPORTING",
        "name": "Weekly Development Progress Report",
        "description": "Produces a comprehensive weekly summary of repository commits and milestones.",
        "goal": "Inspect weekly Git activity, summarize commit milestones, and prepare development status report.",
        "trigger_type": "cron",
        "trigger_config": {"cron_expr": "0 17 * * 5", "schedule_label": "Every Friday at 5:00 PM"},
        "allowed_tools": ["git_ops", "file_read"],
        "planned_actions": [
            "Query weekly commit log and authors",
            "Analyze files modified across recent commits",
            "Synthesize weekly accomplishment report",
        ],
    },
]


@router.get("/automations/templates")
async def get_automation_templates() -> dict[str, Any]:
    """Retrieve curated starter templates for the Automation Center."""
    return {"templates": AUTOMATION_TEMPLATES}


@router.post("/automations/interpret")
async def interpret_automation_prompt(req: AutomationInterpretRequest) -> dict[str, Any]:
    """
    Transform natural language user prompts into a structured automation configuration
    with parsed triggers, scope, goals, and planned actions.
    """
    text = req.prompt.strip()
    text_lower = text.lower()

    # 1. Determine Trigger Type & Schedule
    trigger_type = "manual"
    trigger_config: dict[str, Any] = {}
    schedule_label = "Manual Trigger (Run on demand)"

    if any(k in text_lower for k in ("every morning", "every day", "daily")):
        trigger_type = "cron"
        trigger_config = {"cron_expr": "0 8 * * *", "schedule_label": "Daily at 08:00 AM"}
        schedule_label = "Daily at 08:00 AM"
    elif "every friday" in text_lower or "weekly" in text_lower:
        trigger_type = "cron"
        trigger_config = {"cron_expr": "0 10 * * 5", "schedule_label": "Weekly on Friday at 10:00 AM"}
        schedule_label = "Weekly on Friday at 10:00 AM"
    elif "every hour" in text_lower:
        trigger_type = "interval"
        trigger_config = {"interval_seconds": 3600, "schedule_label": "Every 1 hour"}
        schedule_label = "Every 1 hour"
    elif "every 30 minutes" in text_lower or "every 30 mins" in text_lower:
        trigger_type = "interval"
        trigger_config = {"interval_seconds": 1800, "schedule_label": "Every 30 minutes"}
        schedule_label = "Every 30 minutes"
    elif any(k in text_lower for k in ("when file changes", "file modified", "on file change")):
        trigger_type = "event"
        trigger_config = {"event_name": "file_modified", "schedule_label": "When file changes"}
        schedule_label = "When file changes"
    elif any(k in text_lower for k in ("when git changes", "on git commit", "repo change")):
        trigger_type = "event"
        trigger_config = {"event_name": "git_commit", "schedule_label": "When repository changes"}
        schedule_label = "When repository changes"

    # 2. Determine Tools & Category
    allowed_tools: list[str] = []
    category = "General"
    planned_actions: list[str] = []

    if any(k in text_lower for k in ("github", "git", "commit", "branch", "repo", "repository", "code change")):
        allowed_tools = ["git_ops"]
        category = "PROJECT"
        name = "GitHub & Codebase Monitor"
        planned_actions = [
            "Access local repository",
            "Inspect Git status and recent commits",
            "Analyze modified lines and changed files",
            "Generate summary and report only meaningful updates",
        ]
    elif any(k in text_lower for k in ("research", "search", "web", "duckduckgo", "news", "trend", "track topic")):
        allowed_tools = ["web_search"]
        category = "RESEARCH"
        name = "Automated Research Agent"
        planned_actions = [
            "Construct search queries for DuckDuckGo",
            "Retrieve top relevant citations and snippets",
            "Analyze and synthesize findings",
            "Format executive briefing report",
        ]
    elif any(k in text_lower for k in ("disk", "cpu", "memory", "health", "system", "performance")):
        allowed_tools = ["system_info"]
        category = "SYSTEM"
        name = "System Performance Monitor"
        planned_actions = [
            "Collect CPU, RAM, and disk utilization",
            "Verify metrics against safety thresholds",
            "Record performance metrics in history",
        ]
    elif any(k in text_lower for k in ("file", "directory", "folder", "watch")):
        allowed_tools = ["directory_ops", "file_read"]
        category = "FILES"
        name = "Directory & File Watcher"
        planned_actions = [
            "Scan target directory filesystem tree",
            "Check for created or modified files",
            "Report file system status",
        ]
    else:
        name = "Custom Autonomous Job"
        planned_actions = [
            f"Analyze goal: {text[:50]}",
            "Select required tools dynamically",
            "Execute actions and observe outputs",
            "Synthesize final results",
        ]

    return {
        "interpreted": True,
        "name": name,
        "description": f"Autonomous job configured from: \"{text}\"",
        "goal": text,
        "category": category,
        "trigger_type": trigger_type,
        "trigger_config": trigger_config,
        "schedule_label": schedule_label,
        "allowed_tools": allowed_tools,
        "permission_scope": {
            "allowed_tools": allowed_tools,
            "network_access": "web_search" in allowed_tools,
            "filesystem_scope": "workspace",
        },
        "planned_actions": planned_actions,
    }


@router.get("/automations")
async def list_automations(status: str | None = None) -> dict[str, Any]:
    """List all automations with real statuses, metrics, and schedule data."""
    from api.deps import get_task_storage
    from tasks.types import TaskState

    storage = get_task_storage()
    all_tasks = await storage.list_tasks()

    if status:
        all_tasks = [t for t in all_tasks if t.status.value.lower() == status.lower()]

    active_count = sum(1 for t in all_tasks if t.status in {TaskState.ACTIVE, TaskState.PENDING})
    running_count = sum(1 for t in all_tasks if t.status == TaskState.RUNNING)
    scheduled_count = sum(1 for t in all_tasks if t.next_run_at is not None and t.status in {TaskState.ACTIVE, TaskState.PENDING})
    failed_count = sum(1 for t in all_tasks if t.status == TaskState.FAILED)
    completed_count = sum(1 for t in all_tasks if t.status == TaskState.COMPLETED)

    return {
        "automations": [t.to_dict() for t in all_tasks],
        "summary": {
            "total": len(all_tasks),
            "active": active_count,
            "running": running_count,
            "scheduled": scheduled_count,
            "failed": failed_count,
            "completed": completed_count,
        },
    }


@router.post("/automations")
async def create_automation(req: AutomationCreateRequest) -> dict[str, Any]:
    """Create, persist, and register an autonomous automation job."""
    from api.deps import get_automation_engine, get_task_manager
    from tasks.types import TaskPriority, TaskState, TriggerConfig, TriggerType

    manager = get_task_manager()
    engine = get_automation_engine()

    try:
        tt = TriggerType(req.trigger_type.lower())
    except ValueError:
        tt = TriggerType.MANUAL

    try:
        pr = TaskPriority(req.priority.lower())
    except ValueError:
        pr = TaskPriority.NORMAL

    trigger = TriggerConfig.from_dict({
        "trigger_type": tt.value,
        **req.trigger_config,
    })

    task = await manager.create_task(
        goal=req.goal,
        name=req.name,
        description=req.description,
        priority=pr,
        trigger=trigger,
        allowed_tools=req.allowed_tools,
        permission_scope=req.permission_scope,
        condition_logic=req.condition_logic,
        project_id=req.project_id,
        status=TaskState.ACTIVE if tt != TriggerType.MANUAL else TaskState.PENDING,
    )

    # Register with real scheduler if time/cron/interval based
    if tt != TriggerType.MANUAL:
        try:
            await engine.schedule_task(task)
        except Exception as e:
            logger.error("failed_to_schedule_automation", task_id=str(task.task_id), error=str(e))

    return task.to_dict()


@router.get("/automations/{automation_id}")
async def get_automation_detail(automation_id: str) -> dict[str, Any]:
    """Get single automation details and execution history."""
    from api.deps import get_task_storage

    storage = get_task_storage()
    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")
    data = task.to_dict()
    # Provide all executions for detail view
    data["execution_history"] = [h.to_dict() for h in task.execution_history]
    return data


@router.put("/automations/{automation_id}")
async def update_automation(automation_id: str, req: AutomationUpdateRequest) -> dict[str, Any]:
    """Update automation settings and refresh schedule."""
    from api.deps import get_automation_engine, get_task_storage
    from tasks.types import TaskPriority, TriggerConfig, TriggerType

    storage = get_task_storage()
    engine = get_automation_engine()
    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")

    if req.name is not None:
        task.name = req.name
    if req.description is not None:
        task.description = req.description
    if req.goal is not None:
        task.goal = req.goal
    if req.allowed_tools is not None:
        task.allowed_tools = req.allowed_tools
    if req.permission_scope is not None:
        task.permission_scope = req.permission_scope
    if req.condition_logic is not None:
        task.condition_logic = req.condition_logic
    if req.priority is not None:
        try:
            task.priority = TaskPriority(req.priority.lower())
        except ValueError:
            pass

    if req.trigger_type is not None or req.trigger_config is not None:
        tt_raw = req.trigger_type or task.trigger.trigger_type.value
        try:
            tt = TriggerType(tt_raw.lower())
        except ValueError:
            tt = TriggerType.MANUAL
        cfg = req.trigger_config if req.trigger_config is not None else task.trigger.to_dict()
        cfg["trigger_type"] = tt.value
        task.trigger = TriggerConfig.from_dict(cfg)

        await engine.unschedule_task(task.task_id)
        if tt != TriggerType.MANUAL and task.is_active:
            await engine.schedule_task(task)

    await storage.save_task(task)
    return task.to_dict()


@router.delete("/automations/{automation_id}")
async def delete_automation(automation_id: str) -> dict[str, Any]:
    """Delete an automation and remove its scheduled job."""
    from api.deps import get_automation_engine, get_task_storage

    engine = get_automation_engine()
    storage = get_task_storage()

    await engine.unschedule_task(automation_id)
    deleted = await storage.delete_task(automation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Automation not found")
    return {"deleted": True, "automation_id": automation_id}


@router.post("/automations/{automation_id}/run")
async def run_automation_now(automation_id: str) -> dict[str, Any]:
    """Immediately trigger an autonomous execution run for this automation."""
    from api.deps import get_task_executor, get_task_storage

    storage = get_task_storage()
    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")

    executor = get_task_executor()
    # Execute asynchronously in background so client gets instant response
    asyncio.create_task(executor.execute_task(task.task_id, trigger_source="manual"))
    return {"status": "started", "task_id": str(task.task_id), "message": "Execution launched autonomously"}


@router.post("/automations/{automation_id}/pause")
async def pause_automation(automation_id: str) -> dict[str, Any]:
    """Pause an automation schedule."""
    from api.deps import get_automation_engine, get_task_storage
    from tasks.types import TaskState

    engine = get_automation_engine()
    storage = get_task_storage()

    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")

    await engine.pause_schedule(automation_id)
    await storage.update_status(automation_id, TaskState.PAUSED)
    return {"status": "paused", "task_id": automation_id}


@router.post("/automations/{automation_id}/resume")
async def resume_automation(automation_id: str) -> dict[str, Any]:
    """Resume a paused automation schedule."""
    from api.deps import get_automation_engine, get_task_storage
    from tasks.types import TaskState, TriggerType

    engine = get_automation_engine()
    storage = get_task_storage()

    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")

    await engine.resume_schedule(automation_id)
    # If not scheduled yet, schedule it
    if task.trigger.trigger_type != TriggerType.MANUAL:
        await engine.schedule_task(task)
    await storage.update_status(automation_id, TaskState.ACTIVE)
    return {"status": "resumed", "task_id": automation_id}


@router.get("/automations/{automation_id}/executions")
async def get_automation_executions(automation_id: str) -> dict[str, Any]:
    """List execution runs for an automation."""
    from api.deps import get_task_storage

    storage = get_task_storage()
    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")
    return {"executions": [h.to_dict() for h in task.execution_history]}


@router.get("/automations/{automation_id}/executions/{exec_id}")
async def get_automation_execution_detail(automation_id: str, exec_id: str) -> dict[str, Any]:
    """Get full step trace for a specific execution run."""
    from api.deps import get_task_storage

    storage = get_task_storage()
    task = await storage.get_task(automation_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automation not found")

    for run in task.execution_history:
        if str(run.run_id) == exec_id:
            return run.to_dict()

    raise HTTPException(status_code=404, detail="Execution run not found")


# Backwards compatibility endpoints
@router.get("/tasks")
async def list_tasks_compat() -> dict[str, Any]:
    """Backward compatibility endpoint for task lists."""
    from api.deps import get_task_storage
    storage = get_task_storage()
    all_tasks = await storage.list_tasks()
    return {"tasks": [t.to_dict() for t in all_tasks]}


# ── Memory ──────────────────────────────────────────────────────────────────

@router.get("/memory")
async def list_memories(
    project_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List stored memories, optionally filtered by project, type, or status."""
    res = list(_memory_store)
    if project_id:
        res = [m for m in res if m.get("project_id") == project_id or m.get("project_id") is None]
    if type:
        res = [m for m in res if m.get("type") == type]
    if status:
        res = [m for m in res if m.get("status") == status]
    return {"memories": res}


@router.post("/memory")
async def create_memory(req: MemoryCreateRequest) -> dict[str, Any]:
    """Store a new memory item."""
    mem_id = f"mem-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    meta: dict[str, Any] = {}
    item: dict[str, Any] = {
        "id": mem_id,
        "content": req.content,
        "type": req.type,
        "confidence": req.confidence,
        "importance": req.importance,
        "source": req.source,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "project_id": req.project_id or "default-project",
        "metadata": meta,
    }
    _memory_store.insert(0, item)
    return item


@router.patch("/memory/{memory_id}")
@router.put("/memory/{memory_id}")
async def update_memory(memory_id: str, req: MemoryUpdateRequest) -> dict[str, Any]:
    """Correct or update an existing memory item."""
    now = datetime.now(timezone.utc).isoformat()
    for m in _memory_store:
        if m["id"] == memory_id:
            if req.content is not None:
                m["content"] = req.content
            if req.type is not None:
                m["type"] = req.type
            if req.confidence is not None:
                m["confidence"] = req.confidence
            if req.importance is not None:
                m["importance"] = req.importance
            if req.status is not None:
                m["status"] = req.status
            m["updated_at"] = now
            return m
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.post("/memory/{memory_id}/toggle")
async def toggle_memory(memory_id: str) -> dict[str, Any]:
    """Toggle memory between active and archived."""
    now = datetime.now(timezone.utc).isoformat()
    for m in _memory_store:
        if m["id"] == memory_id:
            m["status"] = "archived" if m.get("status") == "active" else "active"
            m["updated_at"] = now
            return m
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete/forget a memory entry permanently."""
    global _memory_store
    _memory_store = [m for m in _memory_store if m["id"] != memory_id]
    return {"deleted": True, "memory_id": memory_id}


@router.get("/memory/graph")
@router.get("/graph")
async def get_knowledge_graph(project_id: str | None = None) -> dict[str, Any]:
    """Return entities and relationships connected to memories and knowledge."""
    # Synthesize entities and relationships from active memories
    entities: list[dict[str, Any]] = [
        {"id": "ent-user", "name": "User", "type": "person", "label": "User"},
        {"id": "ent-kora", "name": "Kora", "type": "agent", "label": "Kora Agent"},
    ]
    relationships: list[dict[str, Any]] = []

    for m in _memory_store:
        if m.get("status") == "archived":
            continue
        mem_id = m["id"]
        mem_type = m.get("type", "fact")
        content = m.get("content", "")
        # Extract keywords as entities
        words = [w.strip(",.!?\"'") for w in content.split() if len(w) > 4 and w.lower() not in {"prefer", "always", "decided", "using", "project", "building"}]
        for w in words[:2]:
            ent_id = f"ent-{w.lower()}"
            if not any(e["id"] == ent_id for e in entities):
                entities.append({
                    "id": ent_id,
                    "name": w,
                    "type": "concept" if mem_type == "decision" else "technology",
                    "label": w,
                })
            relationships.append({
                "source": "User",
                "target": w,
                "type": "prefers" if "pref" in mem_type else ("decided" if "dec" in mem_type else "associated_with"),
                "confidence": m.get("confidence", 0.9),
                "memory_id": mem_id,
            })

    return {
        "entities": entities,
        "relationships": relationships,
        "entity_count": len(entities),
        "relationship_count": len(relationships),
    }


# ── Research ────────────────────────────────────────────────────────────────

@router.post("/research")
async def perform_research(
    req: ResearchRequest,
    research_router: ResearchRouter = Depends(get_research_router),
) -> dict[str, Any]:
    """
    Execute DuckDuckGo live search and return normalized results.
    """
    try:
        res = await research_router.search(query=req.query, max_results=req.max_results)
        results = []
        for r in getattr(res, "results", []):
            results.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "score": getattr(r, "score", 1.0),
            })
        return {
            "query": req.query,
            "results": results,
            "count": len(results),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research search failed: {exc}")


# ── Tools & Commands ────────────────────────────────────────────────────────
@router.get("/tools")
async def list_tools(tool_registry: ToolRegistry = Depends(get_tool_registry)) -> dict[str, Any]:
    """
    Return all registered agent tools and slash commands dynamically from ToolRegistry.
    """
    tools_data = [
        {
            "name": "search",
            "title": "/search",
            "description": "Query DuckDuckGo for live external evidence & docs",
            "category": "research",
            "icon": "travel_explore_rounded",
        },
        {
            "name": "research",
            "title": "/research",
            "description": "Deep multi-source web research & evidence synthesis",
            "category": "research",
            "icon": "bolt_rounded",
        },
        {
            "name": "rag",
            "title": "/rag",
            "description": "Query indexed local workspace files & code chunks",
            "category": "rag",
            "icon": "folder_open_rounded",
        },
    ]

    for tool in tool_registry.all():
        tools_data.append({
            "name": tool.tool_id or tool.name,
            "title": f"/{tool.tool_id or tool.name}",
            "description": tool.description,
            "category": tool.category.value if hasattr(tool.category, "value") else str(tool.category),
            "icon": "build_circle_rounded",
        })

    return {"tools": tools_data}


def record_activity_entry(event_type: str, details: str, latency_ms: int = 0) -> None:
    """Record an activity log item into the in-memory activity store."""
    entry = {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "details": details,
        "latency_ms": latency_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _activity_store.insert(0, entry)
    if len(_activity_store) > 200:
        _activity_store.pop()


# Connect SystemMonitor activity recorder
try:
    from observability.system_monitor import get_system_monitor
    get_system_monitor().set_activity_recorder(record_activity_entry)
except Exception:
    pass


@router.get("/activity")
async def list_activity() -> dict[str, Any]:
    """List recent agent activity and execution logs."""
    return {"activity": _activity_store}


# ── System Resource Telemetry ───────────────────────────────────────────────

@router.get("/system/metrics")
async def get_system_metrics() -> dict[str, Any]:
    """Retrieve the latest real-time host system resource metrics."""
    from observability.system_monitor import get_system_monitor
    monitor = get_system_monitor()
    return monitor.get_latest_metrics()


@router.get("/system/load")
async def get_system_load() -> dict[str, Any]:
    """Retrieve host load status for resource-aware agent decisions."""
    from observability.system_monitor import get_system_monitor
    monitor = get_system_monitor()
    metrics = monitor.get_latest_metrics()
    return {
        "is_heavy_load": monitor.is_system_under_heavy_load(),
        "cpu_percent": metrics.get("cpu", {}).get("percent", 0.0),
        "ram_percent": metrics.get("memory", {}).get("percent", 0.0),
        "load_summary": metrics.get("load", {}).get("summary", "Normal"),
    }
