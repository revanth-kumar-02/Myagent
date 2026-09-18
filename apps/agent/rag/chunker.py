"""
rag.chunker — Structural Chunker

Responsibilities:
  - Accept a ParsedDocument and produce a list of Chunks
  - Use structure-aware strategies per document type:
      CODE     → function/class boundary splitting
      MARKDOWN → heading-hierarchy splitting
      DOCUMENT → paragraph/section/page/slide splitting
      PLAIN    → sliding window (token-based)
  - Each chunk carries full provenance metadata
  - Respects chunk_size_tokens and chunk_overlap_tokens from settings
  - Never embeds or stores chunks — that is the Embedder/Indexer's job

All chunking strategies target token counts (via tiktoken), not character counts.
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

# Use cl100k_base as a universal token counter (approximate for all models)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


# Regex patterns for identifying code symbol definitions across multiple languages
_CODE_SPLIT_PATTERNS = [
    # Python: def / async def / class
    re.compile(r"^(?:async\s+)?(?:def|class)\s+([a-zA-Z0-9_]+)", re.MULTILINE),
    # JS/TS/Dart/Java/Kotlin: class / interface / function / enum / struct
    re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|enum|struct|type)\s+([a-zA-Z0-9_]+)",
        re.MULTILINE,
    ),
    # C/C++/Go/Rust: fn / func / void / int / etc.
    re.compile(r"^(?:pub\s+)?(?:fn|func)\s+([a-zA-Z0-9_]+)", re.MULTILINE),
]

_MD_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class StructuralChunker:
    """
    Converts a ParsedDocument into a list of Chunks using structure-aware splitting.
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
        Dispatch to the appropriate chunking strategy and return Chunks.
        """
        if not doc.content.strip():
            return []

        match doc.doc_type:
            case DocumentType.CODE:
                return self._chunk_code(doc)
            case DocumentType.MARKDOWN:
                return self._chunk_markdown(doc)
            case DocumentType.DOCUMENT | DocumentType.SPREADSHEET:
                return self._chunk_document(doc)
            case DocumentType.PLAIN:
                return self._chunk_sliding_window(doc)
            case _:
                return self._chunk_sliding_window(doc)

    # ── Private strategies ─────────────────────────────────────────────────────

    def _chunk_code(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at function/class boundaries.
        Falls back to sliding window for files with no clear boundaries.
        Metadata includes: symbol, start_line, end_line, language.
        """
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        # Find boundary lines (0-indexed line indices)
        boundaries: list[tuple[int, str]] = []  # (line_idx, symbol_name)

        for line_idx, line in enumerate(lines):
            for pattern in _CODE_SPLIT_PATTERNS:
                match = pattern.match(line)
                if match:
                    boundaries.append((line_idx, match.group(1)))
                    break

        if not boundaries or len(boundaries) == 1 and boundaries[0][0] == 0:
            # Check if entire file fits in one chunk
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

        # Include header preamble if boundaries don't start at line 0
        sections: list[tuple[int, int, str | None]] = []  # (start_line_idx, end_line_idx, symbol)
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
                # Sub-split oversized sections using sliding window
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

    def _chunk_markdown(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at heading boundaries (h1 > h2 > h3 hierarchy).
        Each chunk includes heading breadcrumb in metadata.
        """
        lines = doc.content.splitlines(keepends=True)
        if not lines:
            return []

        heading_indices: list[tuple[int, int, str]] = []  # (line_idx, level, text)
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

        # Build sections with active breadcrumbs
        sections: list[tuple[int, int, list[str], int]] = []  # (start_line, end_line, breadcrumbs, level)
        heading_stack: list[tuple[int, str]] = []  # (level, text)

        # Optional preamble
        if heading_indices[0][0] > 0:
            sections.append((0, heading_indices[0][0] - 1, ["Document Overview"], 0))

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
                    extra_meta={"headings": breadcrumbs, "level": level},
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks

    def _chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at paragraph/section boundaries or sheet/page boundaries.
        Falls back to sliding window for dense text.
        """
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
                # Flush pending paragraphs first
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

                # Sub-split the oversized paragraph
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

    def _chunk_sliding_window(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Token-based sliding window with overlap.
        Used for plain text and as fallback for other types.
        """
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
        """
        Helper that slides a token window over a sequence of lines, preserving line numbers.
        """
        chunks: list[Chunk] = []
        token_lines: list[tuple[list[int], str, int]] = []  # (tokens, line_text, 1-based line num)

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
                # Single line exceeds chunk size; hard slice its tokens
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

            # Calculate step with overlap
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
        extra_metadata: dict | None = None,
    ) -> Chunk:
        metadata = {**doc.metadata, **(extra_metadata or {})}
        return Chunk(
            chunk_index=index,
            content=content,
            doc_type=doc.doc_type,
            file_path=doc.file_path,
            project_id=self.project_id,
            metadata=metadata,
        )
