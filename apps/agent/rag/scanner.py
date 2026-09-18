"""
rag.scanner — File System Scanner

Responsibilities:
  - Walk a project root directory recursively
  - Compute SHA-256 content hash for each file
  - Compare against indexed_files table in PostgreSQL
  - Emit FileEvents for added, changed, deleted, and skipped files
  - Respect ignore patterns (configurable per project)

This component is the entry point of the ingestion pipeline.
It never reads file content beyond what is needed for hashing.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import AsyncIterator, TYPE_CHECKING

import aiofiles
import structlog

from rag.types import FileEvent, FileEventType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Default patterns to ignore during scanning
DEFAULT_IGNORE_PATTERNS: frozenset[str] = frozenset({
    ".git", ".svn", ".hg",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "env",
    "build", "dist", ".dart_tool", ".flutter-plugins",
    "*.pyc", "*.pyo", "*.egg-info",
    ".DS_Store", "Thumbs.db",
})

# File extensions we can parse (anything else is skipped)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    # Code
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".dart",
    # Markup / Config
    ".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".json", ".xml",
    ".html", ".css", ".sh", ".bash",
    # Documents
    ".pdf", ".docx", ".pptx",
})


class Scanner:
    """
    Walks a project root and emits FileEvents by comparing against the DB state.
    """

    def __init__(
        self,
        project_id: uuid.UUID,
        root_path: Path,
        db: "AsyncSession",
        ignore_patterns: frozenset[str] | None = None,
    ) -> None:
        self.project_id = project_id
        self.root_path = root_path.resolve()
        self._db = db
        self._ignore = ignore_patterns or DEFAULT_IGNORE_PATTERNS

    async def scan(self) -> AsyncIterator[FileEvent]:
        """
        Yield FileEvents for all changed, added, and deleted files.

        Algorithm:
          1. Walk filesystem → compute hash for each supported file
          2. Load known file hashes from indexed_files WHERE project_id = ?
          3. Diff: new files → ADDED, hash mismatch → CHANGED, missing → DELETED
        """
        raise NotImplementedError  # TODO: implement in feature phase

    @staticmethod
    async def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file asynchronously."""
        sha256 = hashlib.sha256()
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _should_ignore(self, path: Path) -> bool:
        """Return True if path or any parent matches an ignore pattern."""
        parts = set(path.parts)
        return bool(parts & self._ignore)
