"""
observability.sanitizer — Sensitive Data & Credential Redaction Subsystem (V14).

Recursively sanitizes traces, events, errors, logs, and diagnostic payloads to prevent leakage of:
  - Passwords, access tokens, API keys (sk-*, ghp_*, bearer tokens)
  - Private keys (RSA/EC/OpenSSH)
  - Sensitive authentication cookies and headers
  - Excessive raw binary data (audio/image byte strings)
"""

from __future__ import annotations

import re
from typing import Any

# Sensitive regex matchers
_PATTERNS = [
    re.compile(r"\b(?:api[_-]?key|apikey|secret|token|password|passwd|auth_token|access_token|private_key)\b\s*[:=]\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|apikey|secret|token|password|passwd|auth_token|access_token|private_key)\b\s*[:=]\s*[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"\b(?:bearer\s+[A-Za-z0-9_\-\.]{16,})\b", re.IGNORECASE),
    re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,})\b", re.IGNORECASE),
    re.compile(r"\b(?:sk-[A-Za-z0-9]{32,}|sk-ant-[A-Za-z0-9_\-]{32,})\b", re.IGNORECASE),
    re.compile(r"(?:-----BEGIN\s+(?:RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY-----[\s\S]+?-----END\s+(?:RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY-----)", re.IGNORECASE),
    re.compile(r"\b(?:set-cookie|cookie)\b\s*[:=]\s*['\"]?[^;\r\n]+['\"]?", re.IGNORECASE),
]

_SENSITIVE_KEY_NAMES = {
    "password", "secret", "token", "apikey", "api_key", "access_token",
    "auth_token", "private_key", "credentials", "cookie", "set-cookie",
}


def mask_sensitive_text(text: str) -> str:
    """Mask credentials and tokens within a string."""
    if not isinstance(text, str):
        return text

    sanitized = text
    for pat in _PATTERNS:
        sanitized = pat.sub("[REDACTED_SECRET]", sanitized)

    # Detect excessive base64 binary dumps
    if len(sanitized) > 2000 and re.search(r"^[A-Za-z0-9+/=]{1000,}$", sanitized):
        return "[REDACTED_BINARY]"

    return sanitized


def sanitize_payload(payload: Any) -> Any:
    """
    Recursively sanitize dictionaries, lists, and primitives.
    """
    if isinstance(payload, str):
        return mask_sensitive_text(payload)

    if isinstance(payload, dict):
        sanitized_dict: dict[str, Any] = {}
        for k, v in payload.items():
            k_str = str(k).lower()
            if any(sens in k_str for sens in _SENSITIVE_KEY_NAMES):
                sanitized_dict[k] = "[REDACTED_SECRET]"
            else:
                sanitized_dict[k] = sanitize_payload(v)
        return sanitized_dict

    if isinstance(payload, (list, tuple, set)):
        return [sanitize_payload(item) for item in payload]

    return payload
