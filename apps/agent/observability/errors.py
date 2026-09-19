"""
observability.errors — Standardized Error Normalization Subsystem (V14).

Normalizes and categorizes errors across RAG, Memory, Web Research, Models, Tools, Database, and Automation.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from observability.sanitizer import mask_sensitive_text, sanitize_payload
from observability.types import ComponentType, ErrorSeverity, NormalizedError

logger = structlog.get_logger(__name__)


class ErrorNormalizer:
    """
    Standardizes disparate exceptions and error logs into typed, sanitized NormalizedError records.
    """

    @classmethod
    def normalize(
        cls,
        error: Exception | str | dict[str, Any],
        component: ComponentType | str = ComponentType.AGENT_CORE,
        trace_id: uuid.UUID | None = None,
        severity: ErrorSeverity | str = ErrorSeverity.ERROR,
        custom_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> NormalizedError:
        """
        Normalize any error input into a secure, sanitized NormalizedError.
        """
        if isinstance(component, str):
            component = ComponentType(component)
        if isinstance(severity, str):
            severity = ErrorSeverity(severity)

        err_msg = ""
        err_details = details or {}

        if isinstance(error, Exception):
            err_msg = f"{type(error).__name__}: {str(error)}"
            if not err_details:
                err_details = {"exception_type": type(error).__name__}
        elif isinstance(error, dict):
            err_msg = str(error.get("message", error.get("error", "Unknown error")))
            err_details = {k: v for k, v in error.items() if k not in ("message", "error")}
        else:
            err_msg = str(error)

        # Sanitize message and details
        sanitized_msg = mask_sensitive_text(err_msg)
        sanitized_details = sanitize_payload(err_details)

        # Derive Standardized Error Code
        code = custom_code or cls._derive_error_code(component, sanitized_msg)

        norm_err = NormalizedError(
            error_code=code,
            component=component,
            message=sanitized_msg,
            severity=severity,
            trace_id=trace_id,
            details=sanitized_details,
        )

        logger.debug(
            "error_normalized",
            error_code=code,
            component=component.value,
            severity=severity.value,
            trace_id=str(trace_id) if trace_id else None,
        )
        return norm_err

    @classmethod
    def _derive_error_code(cls, component: ComponentType, msg: str) -> str:
        """Heuristically derive standardized error code based on component and error string."""
        msg_low = msg.lower()
        prefix = f"ERR_{component.value.upper()}"

        if "timeout" in msg_low:
            return f"{prefix}_TIMEOUT"
        if "permission" in msg_low or "denied" in msg_low:
            return f"{prefix}_PERMISSION_DENIED"
        if "not found" in msg_low or "no such" in msg_low:
            return f"{prefix}_NOT_FOUND"
        if "rate limit" in msg_low or "quota" in msg_low:
            return f"{prefix}_RATE_LIMIT"
        if "connection" in msg_low or "unreachable" in msg_low:
            return f"{prefix}_CONNECTION_FAILED"
        if "syntax" in msg_low or "parse" in msg_low or "malformed" in msg_low:
            return f"{prefix}_PARSE_ERROR"
        if "validation" in msg_low or "invalid" in msg_low:
            return f"{prefix}_VALIDATION_FAILED"

        return f"{prefix}_EXECUTION_FAILED"
