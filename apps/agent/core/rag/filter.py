import os
from pathlib import Path
from typing import Optional
from core.memory import contains_secret

# Directories to ignore during scanning
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "build",
    "dist",
    "out",
    "target",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "coverage",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".cache",
    ".agents"
}

# Supported extensions mapped to canonical language identifiers
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".less": "css",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sql": "sql",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".dart": "dart",
}

# Binary & generated artifact extensions to unconditionally skip
IGNORED_EXTENSIONS = {
    ".exe", ".bin", ".dll", ".so", ".dylib", ".class", ".jar",
    ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".bz2",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".wav", ".mp4", ".mov", ".avi",
    ".wasm", ".db", ".sqlite", ".sqlite3",
    ".lock", ".suo", ".obj", ".o"
}

# Secret / credential file patterns
SECRET_FILENAME_PATTERNS = {
    ".env", "id_rsa", "id_ed25519", "credentials.json", "token.json"
}

MAX_FILE_SIZE_BYTES = 512 * 1024  # 500 KB limit for project RAG ingestion

def is_ignored_directory(dir_name: str) -> bool:
    """Check if directory name matches ignore rules."""
    lower = dir_name.lower()
    return lower in IGNORED_DIRS or lower.startswith(".git") or lower.startswith(".venv")

def get_file_language(file_path: Path) -> Optional[str]:
    """Returns normalized language if file extension is supported, else None."""
    ext = file_path.suffix.lower()
    return SUPPORTED_EXTENSIONS.get(ext)

def is_secret_file(file_path: Path) -> bool:
    """Checks if filename indicates secret credentials."""
    name_lower = file_path.name.lower()
    if name_lower in SECRET_FILENAME_PATTERNS or name_lower.startswith(".env"):
        return True
    if name_lower.endswith((".pem", ".key", ".pfx", ".p12", ".cer")):
        return True
    return False

def is_minified_or_generated(content: str) -> bool:
    """Detect minified code or huge single-line bundle outputs."""
    lines = content.splitlines()
    if not lines:
        return False
    # If file has lines > 1500 chars with few lines, likely minified bundle
    avg_line_len = len(content) / max(1, len(lines))
    if avg_line_len > 800:
        return True
    for line in lines[:20]:
        if len(line) > 2000 and " " not in line[:100]:
            return True
    return False

def should_index_file(file_path: Path, content: Optional[str] = None) -> bool:
    """
    Decides whether a file should be indexed into Project RAG.
    Checks extension, size, secrecy, and generated bundle heuristics.
    """
    ext = file_path.suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return False

    lang = get_file_language(file_path)
    if not lang:
        return False

    if is_secret_file(file_path):
        return False

    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES or size == 0:
            return False
    except OSError:
        return False

    if content is not None:
        if contains_secret(content):
            return False
        if is_minified_or_generated(content):
            return False

    return True
