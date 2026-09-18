"""
rag.scanner — File System Scanner

Responsibilities:
  - Walk a project root directory recursively
  - Compute SHA-256 content hash for each file
  - Compare against indexed_files table in PostgreSQL
  - Emit FileEvents for added, changed, deleted, and skipped files
  - Respect ignore patterns (configurable per project)
  - Skip files that exceed MAX_FILE_SIZE_BYTES

This component is the entry point of the ingestion pipeline.
It never reads file content beyond what is needed for hashing.
"""

from __future__ import annotations

import fnmatch
import hashlib
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, TYPE_CHECKING

import aiofiles
import structlog

from rag.types import FileEvent, FileEventType, MAX_FILE_SIZE_BYTES

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Default directory/file names to ignore during scanning
DEFAULT_IGNORE_PATTERNS: frozenset[str] = frozenset({
    ".git", ".svn", ".hg",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "env", ".env",
    "build", "dist", ".dart_tool", ".flutter-plugins", ".pub-cache",
    "*.pyc", "*.pyo", "*.egg-info",
    ".DS_Store", "Thumbs.db",
    # Secrets / credentials
    "*.pem", "*.key", "*.p12", "*.pfx",
    ".env.local", ".env.production",
    # Generated / large binaries
    "*.lock",
})

# File extensions we can parse (anything else is skipped)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    # Code
    ".py", ".ts", ".tsx", ".js", ".jsx", ".dart",
    ".java", ".kt", ".html", ".css", ".sql",
    # Data / Config
    ".json", ".yaml", ".yml", ".xml", ".csv", ".txt",
    # Documents
    ".md", ".pdf", ".doc", ".docx",
    # Spreadsheets
    ".xls", ".xlsx",
    # Presentations
    ".ppt", ".pptx",
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
        max_file_size: int = MAX_FILE_SIZE_BYTES,
    ) -> None:
        self.project_id = project_id
        self.root_path = root_path.resolve()
        self._db = db
        self._ignore = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        self._max_file_size = max_file_size

    async def scan(self) -> AsyncIterator[FileEvent]:
        """
        Yield FileEvents for all changed, added, and deleted files.

        Algorithm:
          1. Load known {file_path: content_hash} from indexed_files WHERE project_id = ?
          2. Walk filesystem — compute hash for each supported, non-ignored, in-size file
          3. Diff: new files → ADDED, hash mismatch → CHANGED, missing → DELETED
        """
        from sqlalchemy import text

        # Step 1: Load known state from DB
        result = await self._db.execute(
            text(
                "SELECT file_path, content_hash FROM indexed_files "
                "WHERE project_id = :pid"
            ),
            {"pid": str(self.project_id)},
        )
        known: dict[str, str] = {row[0]: row[1] for row in result.fetchall()}
        seen: set[str] = set()

        # Step 2: Walk filesystem
        for path in sorted(self.root_path.rglob("*")):
            if not path.is_file():
                continue
            if self._should_ignore(path):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            rel_path = str(path.relative_to(self.root_path))
            file_size = path.stat().st_size

            # Skip oversized files
            if file_size > self._max_file_size:
                logger.info("scanner_skip_large", path=rel_path, size=file_size)
                yield FileEvent(
                    file_path=rel_path,
                    event_type=FileEventType.SKIPPED,
                    content_hash=None,
                    file_size=file_size,
                )
                continue

            content_hash = await self._hash_file(path)
            seen.add(rel_path)

            if rel_path not in known:
                logger.debug("scanner_added", path=rel_path)
                yield FileEvent(
                    file_path=rel_path,
                    event_type=FileEventType.ADDED,
                    content_hash=content_hash,
                    file_size=file_size,
                )
            elif known[rel_path] != content_hash:
                logger.debug("scanner_changed", path=rel_path)
                yield FileEvent(
                    file_path=rel_path,
                    event_type=FileEventType.CHANGED,
                    content_hash=content_hash,
                    file_size=file_size,
                )
            else:
                # Unchanged — no yield (fully skipped)
                pass

        # Step 3: Emit DELETED for files no longer on disk
        for rel_path in known:
            if rel_path not in seen:
                logger.debug("scanner_deleted", path=rel_path)
                yield FileEvent(
                    file_path=rel_path,
                    event_type=FileEventType.DELETED,
                    content_hash=None,
                )

    @staticmethod
    async def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file asynchronously."""
        sha256 = hashlib.sha256()
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _should_ignore(self, path: Path) -> bool:
        """
        Return True if the path or any ancestor component matches an ignore pattern.
        Supports both exact names and glob patterns (e.g., '*.pyc').
        """
        # Check every part of the path relative to root
        try:
            parts = path.relative_to(self.root_path).parts
        except ValueError:
            parts = path.parts

        for pattern in self._ignore:
            for part in parts:
                if fnmatch.fnmatch(part, pattern) or part == pattern:
                    return True
        return False
