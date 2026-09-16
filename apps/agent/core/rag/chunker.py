import ast
import re
import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RawChunk(BaseModel):
    chunk_index: int
    symbol: Optional[str] = None
    language: str
    content: str
    content_hash: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None

MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 60
CHUNK_OVERLAP_CHARS = 150

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

def subchunk_text(text: str, symbol: Optional[str], language: str, base_index: int) -> List[RawChunk]:
    """Subdivides overly long text blocks while preserving logical boundaries where possible."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [
            RawChunk(
                chunk_index=base_index,
                symbol=symbol,
                language=language,
                content=text,
                content_hash=compute_hash(text)
            )
        ]

    chunks = []
    lines = text.splitlines(keepends=True)
    current_buf = []
    current_len = 0
    sub_idx = 0

    for line in lines:
        if current_len + len(line) > MAX_CHUNK_CHARS and current_buf:
            c_text = "".join(current_buf).strip()
            if c_text:
                sym = f"{symbol} (part {sub_idx + 1})" if symbol else f"Part {sub_idx + 1}"
                chunks.append(
                    RawChunk(
                        chunk_index=base_index + sub_idx,
                        symbol=sym,
                        language=language,
                        content=c_text,
                        content_hash=compute_hash(c_text)
                    )
                )
                sub_idx += 1
            # Keep overlap
            overlap_lines = []
            overlap_len = 0
            for l in reversed(current_buf):
                if overlap_len + len(l) < CHUNK_OVERLAP_CHARS:
                    overlap_lines.insert(0, l)
                    overlap_len += len(l)
                else:
                    break
            current_buf = overlap_lines
            current_len = overlap_len

        current_buf.append(line)
        current_len += len(line)

    if current_buf:
        c_text = "".join(current_buf).strip()
        if c_text:
            sym = f"{symbol} (part {sub_idx + 1})" if (symbol and sub_idx > 0) else symbol
            chunks.append(
                RawChunk(
                    chunk_index=base_index + sub_idx,
                    symbol=sym,
                    language=language,
                    content=c_text,
                    content_hash=compute_hash(c_text)
                )
            )

    return chunks

class StructuralChunker:
    """Language-aware parser and structural chunker."""

    def chunk(self, content: str, language: str) -> List[RawChunk]:
        clean_content = content.strip()
        if not clean_content:
            return []

        lang = language.lower()

        if lang == "python":
            return self._chunk_python(clean_content)
        elif lang in ("javascript", "typescript"):
            return self._chunk_js_ts(clean_content, lang)
        elif lang == "markdown":
            return self._chunk_markdown(clean_content)
        elif lang == "sql":
            return self._chunk_sql(clean_content)
        elif lang == "html":
            return self._chunk_html(clean_content)
        elif lang == "css":
            return self._chunk_css(clean_content)
        elif lang in ("json", "yaml"):
            return self._chunk_data_format(clean_content, lang)
        elif lang in ("java", "kotlin", "dart"):
            return self._chunk_typed_oop(clean_content, lang)
        else:
            return self._chunk_generic(clean_content, lang)

    def _chunk_python(self, content: str) -> List[RawChunk]:
        """Python structural chunker using standard library AST."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._chunk_generic(content, "python")

        lines = content.splitlines(keepends=True)
        chunks: List[RawChunk] = []
        chunk_idx = 0

        # Check for top-level docstring or module header
        first_statement_line = None
        for node in tree.body:
            if hasattr(node, "lineno"):
                first_statement_line = node.lineno
                break

        if first_statement_line and first_statement_line > 1:
            header_text = "".join(lines[:first_statement_line - 1]).strip()
            if len(header_text) >= MIN_CHUNK_CHARS:
                sub = subchunk_text(header_text, "module_header", "python", chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        for node in tree.body:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is None or end is None:
                continue

            node_text = "".join(lines[start - 1:end]).strip()
            if not node_text:
                continue

            symbol = None
            if isinstance(node, ast.ClassDef):
                symbol = f"class {node.name}"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = f"def {node.name}"
            elif isinstance(node, ast.Assign):
                targets = [getattr(t, "id", None) for t in node.targets if hasattr(t, "id")]
                if targets:
                    symbol = f"var {', '.join(targets)}"
                else:
                    symbol = "assignment"
            else:
                symbol = type(node).__name__.lower()

            sub = subchunk_text(node_text, symbol, "python", chunk_idx)
            for c in sub:
                c.start_line = start
                c.end_line = end
            chunks.extend(sub)
            chunk_idx += len(sub)

        if not chunks:
            return self._chunk_generic(content, "python")

        return chunks

    def _chunk_js_ts(self, content: str, language: str) -> List[RawChunk]:
        """Structural chunker for JS/TS/JSX/TSX identifying classes, functions, components, and types."""
        pattern = re.compile(
            r"(?m)^(?P<prefix>\s*(?:export\s+(?:default\s+)?)?)"
            r"(?:(?P<class>class\s+([A-Za-z0-9_]+))|"
            r"(?P<func>(?:async\s+)?function\s+([A-Za-z0-9_]+))|"
            r"(?P<const>(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>)|"
            r"(?P<interface>interface\s+([A-Za-z0-9_]+))|"
            r"(?P<type>type\s+([A-Za-z0-9_]+)\s*=)|"
            r"(?P<enum>enum\s+([A-Za-z0-9_]+)))"
        )

        matches = list(pattern.finditer(content))
        if not matches:
            return self._chunk_generic(content, language)

        chunks: List[RawChunk] = []
        chunk_idx = 0

        # If prefix code exists before first match
        if matches[0].start() > 0:
            prefix_content = content[:matches[0].start()].strip()
            if len(prefix_content) >= MIN_CHUNK_CHARS:
                sub = subchunk_text(prefix_content, "imports_and_globals", language, chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            block_text = content[start_pos:end_pos].strip()

            # Determine symbol name
            symbol = None
            for g in ["class", "func", "const", "interface", "type", "enum"]:
                val = match.group(g)
                if val:
                    # Clean symbol representation
                    clean_sym = re.sub(r"\s+", " ", val.replace("export", "").replace("default", "")).strip()
                    clean_sym = clean_sym.split("=")[0].strip()
                    symbol = clean_sym
                    break

            sub = subchunk_text(block_text, symbol or "declaration", language, chunk_idx)
            chunks.extend(sub)
            chunk_idx += len(sub)

        return chunks

    def _chunk_markdown(self, content: str) -> List[RawChunk]:
        """Markdown structural chunker using section headers."""
        pattern = re.compile(r"(?m)^(?P<hashes>#{1,6})\s+(?P<title>.+)$")
        matches = list(pattern.finditer(content))

        if not matches:
            return self._chunk_generic(content, "markdown")

        chunks: List[RawChunk] = []
        chunk_idx = 0

        # Intro text before first heading
        if matches[0].start() > 0:
            intro = content[:matches[0].start()].strip()
            if len(intro) >= MIN_CHUNK_CHARS:
                sub = subchunk_text(intro, "intro", "markdown", chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            sec_text = content[start_pos:end_pos].strip()
            title = f"{match.group('hashes')} {match.group('title').strip()}"

            sub = subchunk_text(sec_text, title, "markdown", chunk_idx)
            chunks.extend(sub)
            chunk_idx += len(sub)

        return chunks

    def _chunk_sql(self, content: str) -> List[RawChunk]:
        """SQL statement parser."""
        pattern = re.compile(
            r"(?im)^\s*(CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|INDEX|FUNCTION|PROCEDURE|TRIGGER)\s+([A-Za-z0-9_.\"]+)|"
            r"ALTER\s+TABLE\s+([A-Za-z0-9_.\"]+)|"
            r"SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM)"
        )
        matches = list(pattern.finditer(content))
        if not matches:
            return self._chunk_generic(content, "sql")

        chunks: List[RawChunk] = []
        chunk_idx = 0
        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            stmt_text = content[start_pos:end_pos].strip()
            sym = match.group(0).strip().splitlines()[0]
            sub = subchunk_text(stmt_text, sym, "sql", chunk_idx)
            chunks.extend(sub)
            chunk_idx += len(sub)

        return chunks

    def _chunk_html(self, content: str) -> List[RawChunk]:
        """HTML chunker based on top-level semantic tags."""
        pattern = re.compile(
            r"(?is)<(?P<tag>header|nav|main|section|article|footer|form|table|div|aside)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>"
        )
        matches = list(pattern.finditer(content))
        if not matches or len(matches) < 2:
            return self._chunk_generic(content, "html")

        chunks: List[RawChunk] = []
        chunk_idx = 0
        for match in matches:
            tag = match.group("tag")
            attrs = match.group("attrs")
            # extract id or class if available
            id_match = re.search(r'id=["\']([^"\']+)["\']', attrs)
            class_match = re.search(r'class=["\']([^"\']+)["\']', attrs)
            sym = f"<{tag}>"
            if id_match:
                sym = f"<{tag}#{id_match.group(1)}>"
            elif class_match:
                sym = f"<{tag}.{class_match.group(1).split()[0]}>"

            block_text = match.group(0).strip()
            if len(block_text) >= MIN_CHUNK_CHARS:
                sub = subchunk_text(block_text, sym, "html", chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        return chunks if chunks else self._chunk_generic(content, "html")

    def _chunk_css(self, content: str) -> List[RawChunk]:
        """CSS rule block chunker."""
        pattern = re.compile(r"(?s)(?P<selector>[^{}]+)\{(?P<rules>[^{}]+)\}")
        matches = list(pattern.finditer(content))
        if not matches or len(matches) < 2:
            return self._chunk_generic(content, "css")

        chunks: List[RawChunk] = []
        chunk_idx = 0
        for match in matches:
            sel = match.group("selector").strip()
            block = match.group(0).strip()
            if len(block) >= MIN_CHUNK_CHARS:
                sub = subchunk_text(block, sel[:60], "css", chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        return chunks if chunks else self._chunk_generic(content, "css")

    def _chunk_data_format(self, content: str, language: str) -> List[RawChunk]:
        """JSON/YAML block chunker."""
        lines = content.splitlines(keepends=True)
        chunks: List[RawChunk] = []
        current_buf = []
        chunk_idx = 0
        current_key = None

        # Look for top-level keys
        key_pattern = re.compile(r'^\s*["\']?([A-Za-z0-9_-]+)["\']?\s*[:=]')

        for line in lines:
            m = key_pattern.match(line)
            if m and (line.startswith(m.group(1)) or line.startswith('"') or line.startswith("'")):
                if current_buf:
                    text = "".join(current_buf).strip()
                    if len(text) >= MIN_CHUNK_CHARS:
                        sub = subchunk_text(text, current_key or "properties", language, chunk_idx)
                        chunks.extend(sub)
                        chunk_idx += len(sub)
                    current_buf = []
                current_key = m.group(1)
            current_buf.append(line)

        if current_buf:
            text = "".join(current_buf).strip()
            if text:
                sub = subchunk_text(text, current_key or "data", language, chunk_idx)
                chunks.extend(sub)
                chunk_idx += len(sub)

        return chunks if chunks else self._chunk_generic(content, language)

    def _chunk_typed_oop(self, content: str, language: str) -> List[RawChunk]:
        """Java / Kotlin / Dart structural chunker."""
        pattern = re.compile(
            r"(?m)^(?P<indent>\s*)(?:(?:public|private|protected|internal|abstract|static|final)\s+)*"
            r"(?:(?P<class>(?:class|interface|enum|record)\s+([A-Za-z0-9_]+))|"
            r"(?P<method>(?:[A-Za-z0-9_<>[\]]+)\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:throws\s+[A-Za-z0-9_, ]+)?\s*\{))"
        )
        matches = list(pattern.finditer(content))
        if not matches:
            return self._chunk_generic(content, language)

        chunks: List[RawChunk] = []
        chunk_idx = 0
        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            block_text = content[start_pos:end_pos].strip()

            sym = match.group("class") or match.group("method") or "definition"
            sym = re.sub(r"\s+", " ", sym).strip().rstrip("{").strip()

            sub = subchunk_text(block_text, sym, language, chunk_idx)
            chunks.extend(sub)
            chunk_idx += len(sub)

        return chunks if chunks else self._chunk_generic(content, language)

    def _chunk_generic(self, content: str, language: str) -> List[RawChunk]:
        """Fallback line-block chunker with overlap."""
        return subchunk_text(content, None, language, 0)

structural_chunker = StructuralChunker()
