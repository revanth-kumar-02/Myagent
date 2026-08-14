import re
from typing import Dict, Any, List, Union

UNTRUSTED_TAG_OPEN = "<untrusted_web_content>"
UNTRUSTED_TAG_CLOSE = "</untrusted_web_content>"

SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(password|passwd|secret|api[_-]?key|bearer\s+[a-z0-9\-._~+/]+=*|token|authorization)', re.IGNORECASE),
]

def wrap_untrusted_content(content: str, max_chars: int = 15000) -> str:
    """
    Wraps web-extracted text into untrusted content XML-like boundaries so the LLM
    never parses webpage text as system instructions.
    """
    truncated = content[:max_chars]
    if len(content) > max_chars:
        truncated += f"\n... [Truncated at {max_chars} characters]"

    return f"{UNTRUSTED_TAG_OPEN}\n{truncated}\n{UNTRUSTED_TAG_CLOSE}"

def sanitize_sensitive_data(value: Any) -> Any:
    """
    Recursively redacts sensitive values (passwords, auth tokens, secret keys)
    from dictionary structures or log parameters.
    """
    if isinstance(value, str):
        # Redact obvious password/token patterns if present in key=val or auth headers
        if any(pat.search(value) for pat in SENSITIVE_PATTERNS) and ("=" in value or ":" in value or "bearer" in value.lower()):
            return "[REDACTED_SENSITIVE_VALUE]"
        return value
    elif isinstance(value, dict):
        sanitized = {}
        for k, v in value.items():
            if any(pat.search(k) for pat in SENSITIVE_PATTERNS):
                sanitized[k] = "******"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(value, list):
        return [sanitize_sensitive_data(item) for item in value]
    return value
