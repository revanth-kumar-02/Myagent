"""
workspace.discovery — Automated Codebase & Project Discovery Engine (V18)

Analyzes an existing project repository to discover:
  - Programming languages and active frameworks
  - Key dependencies and manifest configurations
  - Important directories, entry points, and configuration files
  - Documentation structure and database migrations
  - Test suites and harness configurations
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import structlog

from workspace.types import ProjectDiscoveryResult

logger = structlog.get_logger(__name__)


class ProjectDiscoveryEngine:
    """
    Scans project filesystem hierarchies to extract factual codebase metadata.
    """

    def discover(self, root_path: str | Path, file_list: Sequence[str] | None = None) -> ProjectDiscoveryResult:
        """
        Analyze project directory or provided file list.
        """
        path = Path(root_path) if isinstance(root_path, str) else root_path

        languages: set[str] = set()
        frameworks: set[str] = set()
        dependencies: list[str] = []
        important_dirs: set[str] = set()
        entry_points: list[str] = []
        config_files: list[str] = []
        doc_files: list[str] = []
        db_configs: list[str] = []
        test_structure: list[str] = []

        # If a pre-scanned file list is provided, analyze paths from it; otherwise scan disk
        relative_paths = list(file_list) if file_list is not None else self._scan_disk(path)

        for rel in relative_paths:
            p = Path(rel)
            name = p.name.lower()
            ext = p.suffix.lower()
            parts = p.parts

            # 1. Languages
            if ext == ".py":
                languages.add("Python")
            elif ext == ".dart":
                languages.add("Dart")
            elif ext in (".ts", ".tsx"):
                languages.add("TypeScript")
            elif ext in (".js", ".jsx"):
                languages.add("JavaScript")
            elif ext == ".rs":
                languages.add("Rust")
            elif ext == ".go":
                languages.add("Go")
            elif ext == ".sql":
                languages.add("SQL")
            elif ext in (".sh", ".bash"):
                languages.add("Shell")

            # 2. Key Directories
            if len(parts) > 1:
                top_dir = parts[0]
                if top_dir in ("apps", "src", "lib", "tests", "test", "docs", "infra", "config", "shared"):
                    important_dirs.add(top_dir)

            # 3. Entry Points
            if name in ("main.py", "app.py", "server.py", "main.dart", "index.ts", "index.js", "main.rs", "main.go"):
                entry_points.append(rel)

            # 4. Config Files
            if name in (
                "pyproject.toml", "pubspec.yaml", "package.json", "dockerfile",
                "docker-compose.yml", "docker-compose.yaml", "cargo.toml", "go.mod",
                "pytest.ini", "requirements.txt", "alembic.ini", ".env.example",
            ):
                config_files.append(rel)

            # 5. Docs
            if ext == ".md" or "docs" in parts:
                doc_files.append(rel)

            # 6. Database / Migrations
            if "migrations" in parts or "sql" in parts or ext == ".sql":
                db_configs.append(rel)

            # 7. Test Structure
            if "tests" in parts or "test" in parts or name.startswith("test_") or name.endswith("_test.dart"):
                test_structure.append(rel)

        # Inspect key manifest files for frameworks/dependencies if disk is accessible
        if path.exists() and path.is_dir():
            self._inspect_manifests(path, config_files, frameworks, dependencies)

        return ProjectDiscoveryResult(
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            dependencies=dependencies[:20],
            important_directories=sorted(important_dirs),
            entry_points=sorted(entry_points),
            config_files=sorted(config_files),
            doc_files=sorted(doc_files),
            db_configs=sorted(db_configs),
            test_structure=sorted(test_structure),
        )

    def _scan_disk(self, root: Path) -> list[str]:
        """Scan directory tree ignoring hidden and vendor folders."""
        if not root.exists() or not root.is_dir():
            return []

        paths: list[str] = []
        ignore_dirs = {".git", ".dart_tool", "node_modules", ".venv", "venv", "__pycache__", "build", ".pytest_cache"}

        try:
            for item in root.rglob("*"):
                if item.is_file():
                    # Check if any parent part is in ignore_dirs
                    rel_parts = set(item.relative_to(root).parts)
                    if not (rel_parts & ignore_dirs):
                        paths.append(str(item.relative_to(root)))
        except Exception as e:
            logger.warning("disk_scan_partial_failure", root=str(root), error=str(e))

        return paths

    def _inspect_manifests(
        self,
        root: Path,
        config_files: list[str],
        frameworks: set[str],
        dependencies: list[str],
    ) -> None:
        """Inspect pyproject.toml, pubspec.yaml, package.json across the project."""
        for cfg in config_files:
            cfg_path = root / cfg
            if not cfg_path.exists():
                continue

            name = cfg_path.name.lower()
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="ignore").lower()
                if name == "pyproject.toml" or name == "requirements.txt":
                    if "fastapi" in content:
                        frameworks.add("FastAPI")
                        dependencies.append("fastapi")
                    if "sqlalchemy" in content:
                        frameworks.add("SQLAlchemy")
                        dependencies.append("sqlalchemy")
                    if "pgvector" in content:
                        frameworks.add("pgvector")
                        dependencies.append("pgvector")
                    if "apscheduler" in content:
                        frameworks.add("APScheduler")
                        dependencies.append("apscheduler")
                    if "playwright" in content:
                        frameworks.add("Playwright")
                        dependencies.append("playwright")

                elif name == "pubspec.yaml":
                    if "flutter" in content:
                        frameworks.add("Flutter")
                    if "flutter_riverpod" in content:
                        frameworks.add("Riverpod")
                        dependencies.append("flutter_riverpod")
                    if "web_socket_channel" in content:
                        dependencies.append("web_socket_channel")

                elif name == "package.json":
                    if "react" in content:
                        frameworks.add("React")
                    if "next" in content:
                        frameworks.add("Next.js")
            except Exception:
                pass

