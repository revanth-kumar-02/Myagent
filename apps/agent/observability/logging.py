"""
observability — Structured logging, tracing, and metrics.

Sets up structlog with JSON output and propagates trace_id through all logs.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, MutableMapping

import structlog

from config import settings
from observability.sanitizer import sanitize_payload


def _sanitizing_processor(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Processor to mask secrets and tokens across all logged keys."""
    return sanitize_payload(event_dict)  # type: ignore[return-value]


def configure_logging() -> None:
    """Call once at application startup to configure structlog."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        _sanitizing_processor,
    ]


    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)  # type: ignore[assignment]

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
