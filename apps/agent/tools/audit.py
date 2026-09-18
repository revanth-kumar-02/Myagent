"""
tools.audit — Tool Execution Audit Logger (V8)

Responsibilities:
  - Record audit trail for all tool invocations (tool_id, action, timestamp, permission, status, duration)
  - Sanitize parameters and outputs to prevent logging secrets, passwords, API keys, or private tokens
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog

from rag.embedder import is_sensitive_content
from tools.types import AuditRecord, PermissionLevel, ToolStatus

logger = structlog.get_logger(__name__)

# Patterns to mask sensitive fields in audit metadata
_SENSITIVE_KEY_PATTERN = re.compile(r"(?:password|secret|api_key|token|auth|credential|private_key)", re.IGNORECASE)


def sanitize_audit_payload(data: Any) -> Any:
    """Recursively mask sensitive values in audit logs."""
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if _SENSITIVE_KEY_PATTERN.search(str(k)):
                sanitized[k] = "****** [REDACTED SECRET]"
            elif isinstance(v, str) and is_sensitive_content(v):
                sanitized[k] = "****** [REDACTED SECRET]"
            else:
                sanitized[k] = sanitize_audit_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_payload(item) for item in data]
    elif isinstance(data, str) and is_sensitive_content(data):
        return "****** [REDACTED SECRET]"
    return data


class ToolAuditLogger:
    """
    In-memory / system audit logger for tool activities.
    """

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(
        self,
        tool_id: str,
        action: str,
        permission_level: PermissionLevel,
        status: ToolStatus,
        execution_duration_ms: int = 0,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """
        Record a sanitized tool audit entry.
        """
        clean_metadata = sanitize_audit_payload(metadata or {})
        clean_error = "****** [REDACTED ERROR]" if error and is_sensitive_content(error) else error

        rec = AuditRecord(
            tool_id=tool_id,
            action=action,
            timestamp=datetime.now(timezone.utc),
            permission_level=permission_level,
            status=status,
            error=clean_error,
            execution_duration_ms=execution_duration_ms,
            metadata=clean_metadata,
        )
        self._records.append(rec)
        logger.info(
            "tool_audit_entry",
            tool_id=tool_id,
            action=action,
            status=status.value,
            duration_ms=execution_duration_ms,
        )
        return rec

    def get_records(self, tool_id: str | None = None, limit: int = 50) -> list[AuditRecord]:
        """Query audit records."""
        if tool_id:
            matching = [r for r in self._records if r.tool_id == tool_id]
            return matching[-limit:]
        return self._records[-limit:]

    def clear(self) -> None:
        """Clear records."""
        self._records.clear()
