"""
rag.chunker — Format-Aware Smart Chunker (RAG V3)

Responsibilities:
  - Format-native chunking strategies:
      Code:           functions, classes, components, interfaces
      Markdown:       heading hierarchies with breadcrumbs
      PDF:            pages and section paragraphs
      Word (DOCX):    sections, headings, tables
      Spreadsheets:   sheets and logical cell ranges / row blocks
      Presentations:  slide-level units
      CSV:            header-aware row groups (headers attached to each batch)
  - Strict token budgeting using tiktoken
  - Preserve rich structural metadata (page_number, sheet_name, slide_number, cell_range, symbol, headings)
  - Only store format-applicable metadata
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog
import tiktoken

from config import settings
from rag.types import Chunk, DocumentType, ParsedDocument

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


_CODE_SPLIT_PATTERNS = [
    re.compile(r"^(?:async\s+)?(?:def|class)\s+([a-zA-Z0-9_]+)", re.MULTILINE),
    re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|enum|struct|type)\s+([a-zA-Z0-9_]+)",
        re.MULTILINE,
    ),
    re.compile(r"^(?:pub\s+)?(?:fn|func)\s+([a-zA-Z0-9_]+)", re.MULTILINE),
]

_MD_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_PAGE_PATTERN = re.compile(r"^\[Page\s+(\d+)(?::\s*([^\]]+))?\]", re.MULTILINE)
_SLIDE_PATTERN = re.compile(r"^\[Slide\s+(\d+)(?::\s*([^\]]+))?\]", re.MULTILINE)
_SHEET_PATTERN = re.compile(r"^\[Sheet:\s*([^|\]]+)(?:\s*\|\s*Range:\s*([^\]]+))?\]", re.MULTILINE)
_CSV_PATTERN = re.compile(r"^\[CSV:\s*([^|\]]+)(?:\s*\|\s*Range:\s*([^\]]+))?\]", re.MULTILINE)


class StructuralChunker:
    """
    Converts a ParsedDocument into a list of Chunks using format-aware smart chunking.
    """

    def __init__(
        self,
        project_id: uuid.UUID,
        chunk_size: int = settings.rag_chunk_size_tokens,
        chunk_overlap: int = settings.rag_chunk_overlap_tokens,
    ) -> None:
        self.project_id = project_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Dispatch to the appropriate format-aware strategy.
        """
        if not doc.content.strip():
            return []

        ext = doc.extension
        file_type = doc.metadata.get("file_type", "")

        # 1. Spreadsheets & CSV
        if file_type == "csv" or ext == ".csv":
            return self._chunk_csv(doc)
        if doc.doc_type == DocumentType.SPREADSHEET or ext in (".xlsx", ".xls"):
            return self._chunk_spreadsheet(doc)

        # 2. Presentations (PPTX)
        if file_type == "pptx" or ext in (".pptx", ".ppt"):
            return self._chunk_presentation(doc)

        # 3. PDF
        if file_type == "pdf" or ext == ".pdf":
            return self._chunk_pdf(doc)

        # 4. Code
        if doc.doc_type == DocumentType.CODE:
            return self._chunk_code(doc)

        # 5. Markdown
        if doc.doc_type == DocumentType.MARKDOWN:
            return self._chunk_markdown(doc)

        # 6. DOCX / General Document
        if doc.doc_type == DocumentType.DOCUMENT:
            return self._chunk_document(doc)

        # 7. Fallback: Sliding Window
        return self._chunk_sliding_window(doc)

    # ── Code Strategy ─────────────────────────────────────────────────────────

    def _chunk_code(self, doc: ParsedDocument) -> list[Chunk]:
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        boundaries: list[tuple[int, str]] = []
        for line_idx, line in enumerate(lines):
            for pattern in _CODE_SPLIT_PATTERNS:
                match = pattern.match(line)
                if match:
                    boundaries.append((line_idx, match.group(1)))
                    break

        if not boundaries or len(boundaries) == 1 and boundaries[0][0] == 0:
            tokens = _count_tokens(doc.content)
            if tokens <= self.chunk_size:
                symbol = boundaries[0][1] if boundaries else None
                return [
                    self._make_chunk(
                        doc,
                        index=0,
                        content=doc.content,
                        extra_metadata={
                            "start_line": 1,
                            "end_line": len(lines),
                            "token_count": tokens,
                            **({"symbol": symbol} if symbol else {}),
                        },
                    )
                ]
            return self._chunk_sliding_window(doc)

        chunks: list[Chunk] = []
        chunk_idx = 0
        sections: list[tuple[int, int, str | None]] = []

        if boundaries[0][0] > 0:
            sections.append((0, boundaries[0][0] - 1, None))

        for i, (b_line, symbol) in enumerate(boundaries):
            end_line = boundaries[i + 1][0] - 1 if i + 1 < len(boundaries) else len(lines) - 1
            sections.append((b_line, end_line, symbol))

        for start_l, end_l, sym in sections:
            sec_lines = lines[start_l : end_l + 1]
            sec_text = "".join(sec_lines)
            tokens = _count_tokens(sec_text)

            if tokens <= self.chunk_size:
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=sec_text,
                        extra_metadata={
                            "start_line": start_l + 1,
                            "end_line": end_l + 1,
                            "token_count": tokens,
                            **({"symbol": sym} if sym else {}),
                        },
                    )
                )
                chunk_idx += 1
            else:
                sub_chunks = self._sub_split_lines(
                    doc,
                    sec_lines,
                    start_line_offset=start_l + 1,
                    base_chunk_index=chunk_idx,
                    extra_meta={"symbol": sym} if sym else {},
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks

    # ── Markdown Strategy ─────────────────────────────────────────────────────

    def _chunk_markdown(self, doc: ParsedDocument) -> list[Chunk]:
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        heading_indices: list[tuple[int, int, str]] = []
        for idx, line in enumerate(lines):
            match = _MD_HEADING_PATTERN.match(line.rstrip("\r\n"))
            if match:
                level = len(match.group(1))
                heading_text = match.group(2).strip()
                heading_indices.append((idx, level, heading_text))

        if not heading_indices:
            return self._chunk_sliding_window(doc)

        chunks: list[Chunk] = []
        chunk_idx = 0
        sections: list[tuple[int, int, list[str], int]] = []
        heading_stack: list[tuple[int, str]] = []

        if heading_indices[0][0] > 0:
            sections.append((0, heading_indices[0][0] - 1, ["Overview"], 0))

        for i, (line_idx, level, h_text) in enumerate(heading_indices):
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, h_text))

            breadcrumbs = [h[1] for h in heading_stack]
            end_line = (
                heading_indices[i + 1][0] - 1
                if i + 1 < len(heading_indices)
                else len(lines) - 1
            )
            sections.append((line_idx, end_line, breadcrumbs, level))

        for start_l, end_l, breadcrumbs, level in sections:
            sec_lines = lines[start_l : end_l + 1]
            sec_text = "".join(sec_lines)
            tokens = _count_tokens(sec_text)

            if tokens <= self.chunk_size:
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=sec_text,
                        extra_metadata={
                            "start_line": start_l + 1,
                            "end_line": end_l + 1,
                            "headings": breadcrumbs,
                            "section": breadcrumbs[-1] if breadcrumbs else None,
                            "level": level,
                            "token_count": tokens,
                        },
                    )
                )
                chunk_idx += 1
            else:
                sub_chunks = self._sub_split_lines(
                    doc,
                    sec_lines,
                    start_line_offset=start_l + 1,
                    base_chunk_index=chunk_idx,
                    extra_meta={"headings": breadcrumbs, "section": breadcrumbs[-1], "level": level},
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks

    # ── PDF Strategy ──────────────────────────────────────────────────────────

    def _chunk_pdf(self, doc: ParsedDocument) -> list[Chunk]:
        """Page-aware and section-aware PDF chunking."""
        page_blocks = re.split(r"(?=\[Page\s+\d+.*?\])", doc.content)
        chunks: list[Chunk] = []
        chunk_idx = 0

        for block in page_blocks:
            block_clean = block.strip()
            if not block_clean:
                continue

            # Extract page number and heading
            page_match = _PAGE_PATTERN.match(block_clean)
            page_num = int(page_match.group(1)) if page_match else None
            heading = page_match.group(2).strip() if (page_match and page_match.group(2)) else None

            tokens = _count_tokens(block_clean)
            if tokens <= self.chunk_size:
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=block_clean,
                        extra_metadata={
                            "page_number": page_num,
                            **({"heading": heading} if heading else {}),
                            "token_count": tokens,
                        },
                    )
                )
                chunk_idx += 1
            else:
                lines = [l + "\n" for l in block_clean.splitlines()]
                sub_chunks = self._sub_split_lines(
                    doc,
                    lines,
                    start_line_offset=1,
                    base_chunk_index=chunk_idx,
                    extra_meta={"page_number": page_num, **({"heading": heading} if heading else {})},
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks or self._chunk_sliding_window(doc)

    # ── Presentation (PPTX) Strategy ──────────────────────────────────────────

    def _chunk_presentation(self, doc: ParsedDocument) -> list[Chunk]:
        """Slide-level chunking for presentations."""
        slide_blocks = re.split(r"(?=\[Slide\s+\d+.*?\])", doc.content)
        chunks: list[Chunk] = []
        chunk_idx = 0

        for block in slide_blocks:
            block_clean = block.strip()
            if not block_clean:
                continue

            slide_match = _SLIDE_PATTERN.match(block_clean)
            slide_num = int(slide_match.group(1)) if slide_match else chunk_idx + 1
            slide_title = slide_match.group(2).strip() if (slide_match and slide_match.group(2)) else None

            tokens = _count_tokens(block_clean)
            if tokens <= self.chunk_size:
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=block_clean,
                        extra_metadata={
                            "slide_number": slide_num,
                            "slide_title": slide_title or f"Slide {slide_num}",
                            "token_count": tokens,
                        },
                    )
                )
                chunk_idx += 1
            else:
                lines = [l + "\n" for l in block_clean.splitlines()]
                sub_chunks = self._sub_split_lines(
                    doc,
                    lines,
                    start_line_offset=1,
                    base_chunk_index=chunk_idx,
                    extra_meta={"slide_number": slide_num, "slide_title": slide_title or f"Slide {slide_num}"},
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks or self._chunk_sliding_window(doc)

    # ── Spreadsheet Strategy ──────────────────────────────────────────────────

    def _chunk_spreadsheet(self, doc: ParsedDocument) -> list[Chunk]:
        """Sheet and cell-range chunking for spreadsheets."""
        sheet_blocks = re.split(r"(?=\[Sheet:\s*.*?\])", doc.content)
        chunks: list[Chunk] = []
        chunk_idx = 0

        for block in sheet_blocks:
            block_clean = block.strip()
            if not block_clean:
                continue

            sheet_match = _SHEET_PATTERN.match(block_clean)
            sheet_name = sheet_match.group(1).strip() if sheet_match else "Sheet1"
            cell_range = sheet_match.group(2).strip() if (sheet_match and sheet_match.group(2)) else None

            lines = block_clean.splitlines(keepends=True)
            header_line = lines[0] if lines else ""
            data_lines = lines[1:] if len(lines) > 1 else lines

            # Batch data rows into chunks under chunk_size tokens
            current_batch: list[str] = []
            current_tokens = _count_tokens(header_line)
            row_start = 1

            for r_idx, row in enumerate(data_lines, start=1):
                row_tokens = _count_tokens(row)
                if current_tokens + row_tokens > self.chunk_size and current_batch:
                    chunk_text = header_line + "".join(current_batch)
                    chunks.append(
                        self._make_chunk(
                            doc,
                            index=chunk_idx,
                            content=chunk_text.strip(),
                            extra_metadata={
                                "sheet_name": sheet_name,
                                "cell_range": cell_range,
                                "row_start": row_start,
                                "row_end": row_start + len(current_batch) - 1,
                                "token_count": current_tokens,
                            },
                        )
                    )
                    chunk_idx += 1
                    row_start = r_idx
                    current_batch = [row]
                    current_tokens = _count_tokens(header_line) + row_tokens
                else:
                    current_batch.append(row)
                    current_tokens += row_tokens

            if current_batch:
                chunk_text = header_line + "".join(current_batch)
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=chunk_text.strip(),
                        extra_metadata={
                            "sheet_name": sheet_name,
                            "cell_range": cell_range,
                            "row_start": row_start,
                            "row_end": row_start + len(current_batch) - 1,
                            "token_count": current_tokens,
                        },
                    )
                )
                chunk_idx += 1

        return chunks or self._chunk_sliding_window(doc)

    # ── CSV Strategy ──────────────────────────────────────────────────────────

    def _chunk_csv(self, doc: ParsedDocument) -> list[Chunk]:
        """Header-aware row group chunking for CSV."""
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        # Preamble header tag
        preamble = ""
        data_rows = lines
        if lines[0].startswith("[CSV:"):
            preamble = lines[0]
            data_rows = lines[1:]

        if not data_rows:
            return []

        csv_header_line = data_rows[0]
        data_rows_only = data_rows[1:]
        headers = doc.metadata.get("headers", [])

        if not data_rows_only:
            # Only header row
            return [
                self._make_chunk(
                    doc,
                    index=0,
                    content=doc.content,
                    extra_metadata={
                        "headers": headers,
                        "row_start": 1,
                        "row_end": 1,
                        "cell_range": doc.metadata.get("cell_range"),
                    },
                )
            ]

        chunks: list[Chunk] = []
        chunk_idx = 0
        current_rows: list[str] = []
        base_header = (preamble + "\n" if preamble else "") + csv_header_line
        base_tokens = _count_tokens(base_header)
        current_tokens = base_tokens
        row_start = 1

        for r_idx, row in enumerate(data_rows_only, start=1):
            r_tokens = _count_tokens(row)
            if current_tokens + r_tokens > self.chunk_size and current_rows:
                chunk_text = base_header + "".join(current_rows)
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=chunk_text.strip(),
                        extra_metadata={
                            "headers": headers,
                            "row_start": row_start,
                            "row_end": row_start + len(current_rows) - 1,
                            "cell_range": doc.metadata.get("cell_range"),
                            "token_count": current_tokens,
                        },
                    )
                )
                chunk_idx += 1
                row_start = r_idx
                current_rows = [row]
                current_tokens = base_tokens + r_tokens
            else:
                current_rows.append(row)
                current_tokens += r_tokens

        if current_rows:
            chunk_text = base_header + "".join(current_rows)
            chunks.append(
                self._make_chunk(
                    doc,
                    index=chunk_idx,
                    content=chunk_text.strip(),
                    extra_metadata={
                        "headers": headers,
                        "row_start": row_start,
                        "row_end": row_start + len(current_rows) - 1,
                        "cell_range": doc.metadata.get("cell_range"),
                        "token_count": current_tokens,
                    },
                )
            )

        return chunks

    # ── General Document Strategy ─────────────────────────────────────────────

    def _chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        paragraphs = re.split(r"\n\s*\n", doc.content)
        if len(paragraphs) <= 1:
            return self._chunk_sliding_window(doc)

        chunks: list[Chunk] = []
        chunk_idx = 0
        current_paragraphs: list[str] = []
        current_tokens = 0
        current_start_line = 1

        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue

            para_tokens = _count_tokens(para_clean)

            if para_tokens > self.chunk_size:
                if current_paragraphs:
                    combined_text = "\n\n".join(current_paragraphs)
                    line_cnt = len(combined_text.splitlines())
                    chunks.append(
                        self._make_chunk(
                            doc,
                            index=chunk_idx,
                            content=combined_text,
                            extra_metadata={
                                "start_line": current_start_line,
                                "end_line": current_start_line + max(0, line_cnt - 1),
                                "token_count": current_tokens,
                            },
                        )
                    )
                    chunk_idx += 1
                    current_start_line += line_cnt + 1
                    current_paragraphs = []
                    current_tokens = 0

                sub_lines = [l + "\n" for l in para_clean.splitlines()]
                sub_chunks = self._sub_split_lines(
                    doc,
                    sub_lines,
                    start_line_offset=current_start_line,
                    base_chunk_index=chunk_idx,
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)
                current_start_line += len(sub_lines) + 1
                continue

            if current_tokens + para_tokens > self.chunk_size and current_paragraphs:
                combined_text = "\n\n".join(current_paragraphs)
                line_cnt = len(combined_text.splitlines())
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=combined_text,
                        extra_metadata={
                            "start_line": current_start_line,
                            "end_line": current_start_line + max(0, line_cnt - 1),
                            "token_count": current_tokens,
                        },
                    )
                )
                chunk_idx += 1
                current_start_line += line_cnt + 1
                current_paragraphs = [para_clean]
                current_tokens = para_tokens
            else:
                current_paragraphs.append(para_clean)
                current_tokens += para_tokens

        if current_paragraphs:
            combined_text = "\n\n".join(current_paragraphs)
            line_cnt = len(combined_text.splitlines())
            chunks.append(
                self._make_chunk(
                    doc,
                    index=chunk_idx,
                    content=combined_text,
                    extra_metadata={
                        "start_line": current_start_line,
                        "end_line": current_start_line + max(0, line_cnt - 1),
                        "token_count": current_tokens,
                    },
                )
            )

        return chunks

    # ── Sliding Window Strategy ───────────────────────────────────────────────

    def _chunk_sliding_window(self, doc: ParsedDocument) -> list[Chunk]:
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        return self._sub_split_lines(
            doc,
            lines,
            start_line_offset=1,
            base_chunk_index=0,
        )

    def _sub_split_lines(
        self,
        doc: ParsedDocument,
        lines: list[str],
        start_line_offset: int,
        base_chunk_index: int,
        extra_meta: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        token_lines: list[tuple[list[int], str, int]] = []

        for idx, line in enumerate(lines):
            line_tokens = _TOKENIZER.encode(line)
            token_lines.append((line_tokens, line, start_line_offset + idx))

        i = 0
        chunk_idx = base_chunk_index

        while i < len(token_lines):
            current_chunk_tokens: list[int] = []
            chunk_line_texts: list[str] = []
            chunk_start_line = token_lines[i][2]
            chunk_end_line = chunk_start_line

            j = i
            while j < len(token_lines):
                line_toks, line_txt, line_num = token_lines[j]
                if current_chunk_tokens and len(current_chunk_tokens) + len(line_toks) > self.chunk_size:
                    break
                current_chunk_tokens.extend(line_toks)
                chunk_line_texts.append(line_txt)
                chunk_end_line = line_num
                j += 1

            if not chunk_line_texts and j < len(token_lines):
                line_toks, line_txt, line_num = token_lines[j]
                sub_toks = line_toks[: self.chunk_size]
                chunk_line_texts.append(_TOKENIZER.decode(sub_toks))
                current_chunk_tokens = sub_toks
                chunk_end_line = line_num
                j += 1

            content = "".join(chunk_line_texts)
            if content.strip():
                chunks.append(
                    self._make_chunk(
                        doc,
                        index=chunk_idx,
                        content=content,
                        extra_metadata={
                            "start_line": chunk_start_line,
                            "end_line": chunk_end_line,
                            "token_count": len(current_chunk_tokens),
                            **(extra_meta or {}),
                        },
                    )
                )
                chunk_idx += 1

            if j >= len(token_lines):
                break

            overlap_tokens = 0
            step_back = 0
            for back_idx in range(j - 1, i, -1):
                overlap_tokens += len(token_lines[back_idx][0])
                if overlap_tokens >= self.chunk_overlap:
                    step_back = j - back_idx
                    break

            i = max(i + 1, j - step_back)

        return chunks

    def _make_chunk(
        self,
        doc: ParsedDocument,
        index: int,
        content: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        # Merge only relevant metadata
        base_meta = {
            "file_name": doc.file_name,
            "file_type": doc.metadata.get("file_type", doc.doc_type.value),
            **doc.metadata,
        }
        # Remove noisy bulk fields from chunk metadata
        base_meta.pop("pages", None)
        base_meta.pop("slides", None)
        base_meta.pop("sheets", None)

        merged = {**base_meta, **(extra_metadata or {})}
        return Chunk(
            chunk_index=index,
            content=content,
            doc_type=doc.doc_type,
            file_path=doc.file_path,
            project_id=self.project_id,
            metadata=merged,
        )
