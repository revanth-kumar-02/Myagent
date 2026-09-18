"""
rag.parser — Document Parser

Responsibilities:
  - Route files to the correct parser by extension
  - Produce a normalised ParsedDocument for every supported file type
  - Extract metadata useful for chunking (headings, language, page/slide numbers)
  - Never perform chunking — that is the Chunker's job

Supported parsers:
  CodeParser        — .py .js .ts .java .kt .dart .html .css .sql
  MarkdownParser    — .md
  PDFParser         — .pdf
  DocxParser        — .docx .doc
  PptxParser        — .pptx .ppt
  SpreadsheetParser — .xls .xlsx
  PlainTextParser   — .json .yaml .yml .xml .csv .txt
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import aiofiles
import chardet
import structlog

from rag.types import DocumentType, ParsedDocument

logger = structlog.get_logger(__name__)

# Extension → DocumentType mapping
_EXT_MAP: dict[str, DocumentType] = {
    # Code
    ".py": DocumentType.CODE, ".ts": DocumentType.CODE,
    ".js": DocumentType.CODE, ".java": DocumentType.CODE,
    ".kt": DocumentType.CODE, ".dart": DocumentType.CODE,
    ".html": DocumentType.CODE, ".css": DocumentType.CODE,
    ".sql": DocumentType.CODE,
    # Markdown
    ".md": DocumentType.MARKDOWN,
    # Documents
    ".pdf": DocumentType.DOCUMENT,
    ".docx": DocumentType.DOCUMENT, ".doc": DocumentType.DOCUMENT,
    ".pptx": DocumentType.DOCUMENT, ".ppt": DocumentType.DOCUMENT,
    # Spreadsheets
    ".xls": DocumentType.SPREADSHEET, ".xlsx": DocumentType.SPREADSHEET,
    # Plain text / config
    ".txt": DocumentType.PLAIN, ".yaml": DocumentType.PLAIN,
    ".yml": DocumentType.PLAIN, ".json": DocumentType.PLAIN,
    ".xml": DocumentType.PLAIN, ".csv": DocumentType.PLAIN,
}

# Language name for code files (used in metadata)
_LANG_MAP: dict[str, str] = {
    ".py": "python", ".ts": "typescript",
    ".js": "javascript", ".java": "java",
    ".kt": "kotlin", ".dart": "dart",
    ".html": "html", ".css": "css",
    ".sql": "sql",
}


class Parser:
    """
    Routes files to the appropriate parser and returns a ParsedDocument.
    """

    async def parse(self, file_path: Path | str) -> ParsedDocument | None:
        """
        Parse a file and return a ParsedDocument, or None if unsupported.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        doc_type = _EXT_MAP.get(ext)
        if doc_type is None:
            logger.debug("parser_skipped_unsupported", path=str(path))
            return None

        try:
            match doc_type:
                case DocumentType.CODE:
                    return await self._parse_code(path, ext)
                case DocumentType.MARKDOWN:
                    return await self._parse_markdown(path)
                case DocumentType.DOCUMENT:
                    return await self._parse_document(path, ext)
                case DocumentType.SPREADSHEET:
                    return await self._parse_spreadsheet(path)
                case DocumentType.PLAIN:
                    return await self._parse_plain(path, ext)
        except Exception as exc:
            logger.warning("parser_error", path=str(file_path), error=str(exc))
            return None

    # ── Code ──────────────────────────────────────────────────────────────────

    async def _parse_code(self, path: Path, ext: str) -> ParsedDocument:
        content = await self._read_text(path)
        language = _LANG_MAP.get(ext, "unknown")
        line_count = content.count("\n") + 1
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.CODE,
            content=content,
            metadata={
                "language": language,
                "line_count": line_count,
                "file_size": path.stat().st_size,
                "extension": ext,
            },
        )

    # ── Markdown ──────────────────────────────────────────────────────────────

    async def _parse_markdown(self, path: Path) -> ParsedDocument:
        content = await self._read_text(path)
        # Extract headings for metadata
        headings: list[dict[str, Any]] = []
        for i, line in enumerate(content.splitlines(), start=1):
            m = re.match(r"^(#{1,6})\s+(.+)", line)
            if m:
                headings.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.MARKDOWN,
            content=content,
            metadata={
                "headings": headings,
                "line_count": content.count("\n") + 1,
                "heading_count": len(headings),
            },
        )

    # ── Documents (PDF / DOCX / PPTX) ────────────────────────────────────────

    async def _parse_document(self, path: Path, ext: str) -> ParsedDocument:
        match ext:
            case ".pdf":
                return await self._parse_pdf(path)
            case ".docx" | ".doc":
                return await self._parse_docx(path)
            case ".pptx" | ".ppt":
                return await self._parse_pptx(path)
        return await self._parse_plain(path, ext)

    async def _parse_pdf(self, path: Path) -> ParsedDocument:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages: list[str] = []
        page_metadata: list[dict[str, Any]] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i}]\n{text}")
                page_metadata.append({"page": i, "char_count": len(text)})
        content = "\n\n".join(pages)
        info = reader.metadata or {}
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=content,
            metadata={
                "page_count": len(reader.pages),
                "pages": page_metadata,
                "title": str(info.get("/Title", "")),
                "author": str(info.get("/Author", "")),
                "extension": ".pdf",
            },
        )

    async def _parse_docx(self, path: Path) -> ParsedDocument:
        import docx as python_docx

        doc = python_docx.Document(str(path))
        sections: list[str] = []
        tables_text: list[str] = []
        headings: list[dict[str, Any]] = []

        line_num = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                line_num += 1
                continue
            # Detect heading styles
            style_name = para.style.name if para.style else ""
            if "Heading" in style_name:
                try:
                    level = int(style_name.split()[-1])
                except (ValueError, IndexError):
                    level = 1
                headings.append({"level": level, "text": text, "line": line_num})
            sections.append(text)
            line_num += 1

        # Extract tables
        for table in doc.tables:
            rows: list[str] = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                tables_text.append("\n".join(rows))

        content = "\n\n".join(sections)
        if tables_text:
            content += "\n\n=== Tables ===\n" + "\n\n".join(tables_text)

        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=content,
            metadata={
                "section_count": len(sections),
                "table_count": len(tables_text),
                "headings": headings,
                "extension": path.suffix.lower(),
            },
        )

    async def _parse_pptx(self, path: Path) -> ParsedDocument:
        from pptx import Presentation
        prs = Presentation(str(path))
        slides_text: list[str] = []
        slide_metadata: list[dict[str, Any]] = []

        for i, slide in enumerate(prs.slides, start=1):
            parts: list[str] = []
            title = ""
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                text = shape.text_frame.text.strip()
                if not text:
                    continue
                if shape.shape_type == 13:  # TITLE
                    title = text
                parts.append(text)
            slide_text = f"[Slide {i}] {title}\n" + "\n".join(parts)
            slides_text.append(slide_text)
            slide_metadata.append({"slide": i, "title": title, "char_count": len(slide_text)})

        content = "\n\n".join(slides_text)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=content,
            metadata={
                "slide_count": len(prs.slides),
                "slides": slide_metadata,
                "extension": path.suffix.lower(),
            },
        )

    # ── Spreadsheets (XLS / XLSX) ─────────────────────────────────────────────

    async def _parse_spreadsheet(self, path: Path) -> ParsedDocument:
        import openpyxl
        ext = path.suffix.lower()

        # openpyxl handles .xlsx natively; for .xls use read-only text fallback
        if ext == ".xls":
            return await self._parse_xls_fallback(path)

        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        all_text: list[str] = []
        sheets_meta: list[dict[str, Any]] = []
        total_rows = 0

        for sheet_name in sheet_names:
            ws = wb[sheet_name]
            rows: list[str] = []
            row_count = 0
            col_count = 0
            for row in ws.iter_rows(values_only=True):
                # Skip entirely empty rows
                values = [str(v) if v is not None else "" for v in row]
                if not any(v.strip() for v in values):
                    continue
                rows.append(" | ".join(values))
                row_count += 1
                col_count = max(col_count, len(values))

            sheet_text = f"[Sheet: {sheet_name}]\n" + "\n".join(rows)
            all_text.append(sheet_text)
            total_rows += row_count
            sheets_meta.append({
                "sheet_name": sheet_name,
                "row_count": row_count,
                "col_count": col_count,
            })

        wb.close()
        content = "\n\n".join(all_text)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.SPREADSHEET,
            content=content,
            metadata={
                "sheet_names": sheet_names,
                "sheet_count": len(sheet_names),
                "total_rows": total_rows,
                "sheets": sheets_meta,
                "extension": ext,
            },
        )

    async def _parse_xls_fallback(self, path: Path) -> ParsedDocument:
        """
        Fallback for legacy .xls files using xlrd if available, else raw text.
        """
        try:
            import xlrd
            wb = xlrd.open_workbook(str(path))
            parts: list[str] = []
            for sheet in wb.sheets():
                rows = []
                for row_i in range(sheet.nrows):
                    cells = [str(sheet.cell_value(row_i, col_i)) for col_i in range(sheet.ncols)]
                    rows.append(" | ".join(cells))
                parts.append(f"[Sheet: {sheet.name}]\n" + "\n".join(rows))
            content = "\n\n".join(parts)
            return ParsedDocument(
                file_path=str(path),
                doc_type=DocumentType.SPREADSHEET,
                content=content,
                metadata={"extension": ".xls", "sheet_count": wb.nsheets},
            )
        except ImportError:
            # xlrd not installed — read raw bytes as best-effort text
            content = await self._read_text(path)
            return ParsedDocument(
                file_path=str(path),
                doc_type=DocumentType.SPREADSHEET,
                content=content,
                metadata={"extension": ".xls", "note": "xlrd not available; raw text extracted"},
            )

    # ── Plain text / config ───────────────────────────────────────────────────

    async def _parse_plain(self, path: Path, ext: str = "") -> ParsedDocument:
        content = await self._read_text(path)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.PLAIN,
            content=content,
            metadata={
                "extension": ext or path.suffix.lower(),
                "line_count": content.count("\n") + 1,
                "char_count": len(content),
            },
        )

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    async def _read_text(path: Path) -> str:
        """Read file content, auto-detecting encoding with chardet."""
        async with aiofiles.open(path, "rb") as f:
            raw = await f.read()
        detected = chardet.detect(raw[:4096])  # sample first 4KB for speed
        encoding = detected.get("encoding") or "utf-8"
        return raw.decode(encoding, errors="replace")
