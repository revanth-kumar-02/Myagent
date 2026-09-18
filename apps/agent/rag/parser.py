"""
rag.parser — Document Parser

Responsibilities:
  - Route files to the correct parser by extension
  - Produce a normalised ParsedDocument for every supported file type
  - Extract metadata useful for chunking (headings, language, encoding)
  - Never perform chunking — that is the Chunker's job

Parser registry:
  .py / .ts / .go / .rs / .java / .kt / .cpp / .cs / .rb / .php / .swift / .dart
    → CodeParser

  .md / .rst
    → MarkdownParser

  .pdf / .docx / .pptx
    → DocumentParser

  .txt / .yaml / .yml / .toml / .json / .xml / .html / .css / .sh / .bash
    → PlainTextParser
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import chardet
import structlog

from rag.types import DocumentType, ParsedDocument

logger = structlog.get_logger(__name__)

# Extension → DocumentType mapping
_EXT_MAP: dict[str, DocumentType] = {
    # Code
    ".py": DocumentType.CODE, ".ts": DocumentType.CODE, ".tsx": DocumentType.CODE,
    ".js": DocumentType.CODE, ".jsx": DocumentType.CODE, ".go": DocumentType.CODE,
    ".rs": DocumentType.CODE, ".java": DocumentType.CODE, ".kt": DocumentType.CODE,
    ".cpp": DocumentType.CODE, ".c": DocumentType.CODE, ".h": DocumentType.CODE,
    ".cs": DocumentType.CODE, ".rb": DocumentType.CODE, ".php": DocumentType.CODE,
    ".swift": DocumentType.CODE, ".dart": DocumentType.CODE,
    # Markdown
    ".md": DocumentType.MARKDOWN, ".rst": DocumentType.MARKDOWN,
    # Documents
    ".pdf": DocumentType.DOCUMENT, ".docx": DocumentType.DOCUMENT, ".pptx": DocumentType.DOCUMENT,
    # Plain text / config
    ".txt": DocumentType.PLAIN, ".yaml": DocumentType.PLAIN, ".yml": DocumentType.PLAIN,
    ".toml": DocumentType.PLAIN, ".json": DocumentType.PLAIN, ".xml": DocumentType.PLAIN,
    ".html": DocumentType.PLAIN, ".css": DocumentType.PLAIN,
    ".sh": DocumentType.PLAIN, ".bash": DocumentType.PLAIN,
}

# Language name for code files (used in metadata)
_LANG_MAP: dict[str, str] = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".go": "go",
    ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".cpp": "cpp", ".c": "c", ".h": "c",
    ".cs": "csharp", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".dart": "dart",
}


class Parser:
    """
    Routes files to the appropriate parser and returns a ParsedDocument.
    """

    async def parse(self, file_path: Path) -> ParsedDocument | None:
        """
        Parse a file and return a ParsedDocument, or None if unsupported.
        """
        ext = file_path.suffix.lower()
        doc_type = _EXT_MAP.get(ext)
        if doc_type is None:
            logger.debug("parser_skipped_unsupported", path=str(file_path))
            return None

        match doc_type:
            case DocumentType.CODE:
                return await self._parse_code(file_path, ext)
            case DocumentType.MARKDOWN:
                return await self._parse_markdown(file_path)
            case DocumentType.DOCUMENT:
                return await self._parse_document(file_path, ext)
            case DocumentType.PLAIN:
                return await self._parse_plain(file_path)

    # ── Private parsers (stubs) ────────────────────────────────────────────────

    async def _parse_code(self, path: Path, ext: str) -> ParsedDocument:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _parse_markdown(self, path: Path) -> ParsedDocument:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _parse_document(self, path: Path, ext: str) -> ParsedDocument:
        raise NotImplementedError  # TODO: implement in feature phase

    async def _parse_plain(self, path: Path) -> ParsedDocument:
        raise NotImplementedError  # TODO: implement in feature phase

    @staticmethod
    async def _read_text(path: Path) -> str:
        """Read file content, auto-detecting encoding."""
        raw = path.read_bytes()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "utf-8"
        return raw.decode(encoding, errors="replace")
