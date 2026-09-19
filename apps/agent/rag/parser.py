"""
rag.parser — Document-Aware Parser (RAG V3)

Responsibilities:
  - Route files to the correct format-aware parser by extension
  - Produce a normalized ParsedDocument for every supported file type
  - Extract rich structural metadata:
      PDF:         pages, headings, paragraphs, tables
      DOC/DOCX:    headings with levels, paragraphs, tables
      XLS/XLSX:    workbooks, sheets, cell ranges, row/column counts
      PPT/PPTX:    slides, titles, text, slide tables
      CSV:         headers, row counts, column counts, tabular data
      Code:        language, lines, symbols
      Markdown:    heading hierarchy with breadcrumbs
"""

from __future__ import annotations

import csv
import io
import os
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
    # Spreadsheets & Tabular Data
    ".xls": DocumentType.SPREADSHEET, ".xlsx": DocumentType.SPREADSHEET,
    ".csv": DocumentType.SPREADSHEET,
    # Plain text / config
    ".txt": DocumentType.PLAIN, ".yaml": DocumentType.PLAIN,
    ".yml": DocumentType.PLAIN, ".json": DocumentType.PLAIN,
    ".xml": DocumentType.PLAIN,
}

# Language name for code files (used in metadata)
_LANG_MAP: dict[str, str] = {
    ".py": "python", ".ts": "typescript",
    ".js": "javascript", ".java": "java",
    ".kt": "kotlin", ".dart": "dart",
    ".html": "html", ".css": "css",
    ".sql": "sql",
}


def _col_num_to_letter(n: int) -> str:
    """Convert 1-based column index to Excel letter (1 -> A, 27 -> AA)."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


class Parser:
    """
    Document-aware parser producing structured ParsedDocuments.
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
                    if ext == ".csv":
                        return await self._parse_csv(path)
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
                "file_name": path.name,
                "file_type": "code",
                "language": language,
                "line_count": line_count,
                "file_size": path.stat().st_size if path.exists() else len(content),
                "extension": ext,
            },
        )

    # ── Markdown ──────────────────────────────────────────────────────────────

    async def _parse_markdown(self, path: Path) -> ParsedDocument:
        content = await self._read_text(path)
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
                "file_name": path.name,
                "file_type": "markdown",
                "headings": headings,
                "line_count": content.count("\n") + 1,
                "heading_count": len(headings),
                "extension": ".md",
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
        pages_content: list[str] = []
        page_metadata: list[dict[str, Any]] = []

        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text_clean = text.strip()
            if not text_clean:
                continue

            # Detect potential heading on this page (first prominent line)
            lines = [l.strip() for l in text_clean.splitlines() if l.strip()]
            page_heading = lines[0] if lines and len(lines[0]) < 80 else None

            page_block = f"[Page {i}" + (f": {page_heading}]" if page_heading else "]") + f"\n{text_clean}"
            pages_content.append(page_block)
            page_metadata.append({
                "page_number": i,
                "char_count": len(text_clean),
                "heading": page_heading,
            })

        content = "\n\n".join(pages_content)
        info = reader.metadata or {}
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=content,
            metadata={
                "file_name": path.name,
                "file_type": "pdf",
                "page_count": len(reader.pages),
                "pages": page_metadata,
                "title": str(info.get("/Title", "") or path.stem),
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

        line_num = 1
        current_heading = None

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                line_num += 1
                continue

            style_name = para.style.name if para.style else ""
            if "Heading" in style_name:
                try:
                    level = int(style_name.split()[-1])
                except (ValueError, IndexError):
                    level = 1
                current_heading = text
                headings.append({"level": level, "text": text, "line": line_num})
                sections.append(f"## {text}")
            else:
                sections.append(text)
            line_num += 1

        # Extract structured tables
        for table_idx, table in enumerate(doc.tables, start=1):
            table_rows: list[str] = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(" | ".join(cells))
            if table_rows:
                table_str = f"[Table {table_idx}]\n" + "\n".join(table_rows)
                tables_text.append(table_str)

        full_content = "\n\n".join(sections)
        if tables_text:
            full_content += "\n\n=== Tables ===\n\n" + "\n\n".join(tables_text)

        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=full_content,
            metadata={
                "file_name": path.name,
                "file_type": "docx",
                "section_count": len(sections),
                "table_count": len(doc.tables),
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
            tables_in_slide: list[str] = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if not text:
                        continue
                    if shape.shape_type == 13 or shape.name.lower().startswith("title") or not title:
                        if not title:
                            title = text.splitlines()[0]
                    parts.append(text)

                elif shape.has_table:
                    table = shape.table
                    rows_str = []
                    for row in table.rows:
                        cells = [c.text.strip() for c in row.cells]
                        rows_str.append(" | ".join(cells))
                    if rows_str:
                        tables_in_slide.append("\n".join(rows_str))

            slide_body = "\n".join(parts)
            if tables_in_slide:
                slide_body += "\n" + "\n".join(tables_in_slide)

            slide_heading = f"[Slide {i}: {title}]" if title else f"[Slide {i}]"
            full_slide_text = f"{slide_heading}\n{slide_body}"
            slides_text.append(full_slide_text)

            slide_metadata.append({
                "slide_number": i,
                "title": title or f"Slide {i}",
                "char_count": len(full_slide_text),
            })

        content = "\n\n".join(slides_text)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.DOCUMENT,
            content=content,
            metadata={
                "file_name": path.name,
                "file_type": "pptx",
                "slide_count": len(prs.slides),
                "slides": slide_metadata,
                "extension": path.suffix.lower(),
            },
        )

    # ── Spreadsheets (XLS / XLSX / CSV) ───────────────────────────────────────

    async def _parse_spreadsheet(self, path: Path) -> ParsedDocument:
        import openpyxl

        ext = path.suffix.lower()
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
            max_cols = 0

            for row in ws.iter_rows(values_only=True):
                values = [str(v) if v is not None else "" for v in row]
                if not any(v.strip() for v in values):
                    continue
                rows.append(" | ".join(values))
                row_count += 1
                max_cols = max(max_cols, len(values))

            end_col_letter = _col_num_to_letter(max(1, max_cols))
            cell_range = f"A1:{end_col_letter}{max(1, row_count)}"

            sheet_header = f"[Sheet: {sheet_name} | Range: {cell_range}]"
            sheet_text = f"{sheet_header}\n" + "\n".join(rows)
            all_text.append(sheet_text)
            total_rows += row_count

            sheets_meta.append({
                "sheet_name": sheet_name,
                "cell_range": cell_range,
                "row_count": row_count,
                "col_count": max_cols,
            })

        wb.close()
        content = "\n\n".join(all_text)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.SPREADSHEET,
            content=content,
            metadata={
                "file_name": path.name,
                "file_type": "spreadsheet",
                "sheet_names": sheet_names,
                "sheet_count": len(sheet_names),
                "total_rows": total_rows,
                "sheets": sheets_meta,
                "extension": ext,
            },
        )

    async def _parse_csv(self, path: Path) -> ParsedDocument:
        """Parse CSV into structured tabular text with headers and cell ranges."""
        raw_text = await self._read_text(path)
        reader = csv.reader(io.StringIO(raw_text))
        rows: list[list[str]] = [r for r in reader if any(cell.strip() for cell in r)]

        if not rows:
            return ParsedDocument(
                file_path=str(path),
                doc_type=DocumentType.SPREADSHEET,
                content="",
                metadata={"file_name": path.name, "file_type": "csv", "headers": [], "row_count": 0},
            )

        headers = [h.strip() for h in rows[0]]
        formatted_rows = [" | ".join(r) for r in rows]
        col_count = len(headers)
        row_count = len(rows) - 1
        end_col = _col_num_to_letter(max(1, col_count))
        cell_range = f"A1:{end_col}{len(rows)}"

        content = f"[CSV: {path.name} | Range: {cell_range}]\n" + "\n".join(formatted_rows)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.SPREADSHEET,
            content=content,
            metadata={
                "file_name": path.name,
                "file_type": "csv",
                "headers": headers,
                "row_count": row_count,
                "col_count": col_count,
                "cell_range": cell_range,
                "extension": ".csv",
            },
        )

    async def _parse_xls_fallback(self, path: Path) -> ParsedDocument:
        try:
            import xlrd  # type: ignore[import-not-found,import-untyped]
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
                metadata={"file_name": path.name, "file_type": "xls", "extension": ".xls", "sheet_count": wb.nsheets},
            )
        except ImportError:
            content = await self._read_text(path)
            return ParsedDocument(
                file_path=str(path),
                doc_type=DocumentType.SPREADSHEET,
                content=content,
                metadata={"file_name": path.name, "file_type": "xls", "extension": ".xls"},
            )

    # ── Plain text / config ───────────────────────────────────────────────────

    async def _parse_plain(self, path: Path, ext: str = "") -> ParsedDocument:
        content = await self._read_text(path)
        return ParsedDocument(
            file_path=str(path),
            doc_type=DocumentType.PLAIN,
            content=content,
            metadata={
                "file_name": path.name,
                "file_type": "plain",
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
        detected = chardet.detect(raw[:4096])
        encoding = detected.get("encoding") or "utf-8"
        return raw.decode(encoding, errors="replace")
