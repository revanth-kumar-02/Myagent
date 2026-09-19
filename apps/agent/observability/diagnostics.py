"""
observability.diagnostics — Structured Root-Cause Failure Diagnostic Engine (V14).

Analyzes failed traces, permission denials, tool exceptions, and retrieval timeouts to formulate actionable fixes.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from observability.tracer import AgentTracer
from observability.types import ComponentType, DiagnosticReport, TraceRecord

logger = structlog.get_logger(__name__)


class DiagnosticEngine:
    """
    Produces structured diagnostic reports with root causes and suggested remediation.
    """

    def __init__(self, tracer: AgentTracer) -> None:
        self.tracer = tracer

    def diagnose_trace(self, trace_id: uuid.UUID) -> DiagnosticReport | None:
        """
        Analyze a failed or degraded execution trace and generate a DiagnosticReport.
        """
        trace = self.tracer.get_trace(trace_id)
        if trace is None:
            return None

        # If trace succeeded without recorded errors, return informational report
        if trace.final_status == "success" and not trace.errors:
            return DiagnosticReport(
                trace_id=trace.trace_id,
                error_code="SUCCESS_NO_ERROR",
                component=ComponentType.AGENT_CORE,
                root_cause="Execution succeeded without errors.",
                failed_action="None",
                suggested_fix="No remediation necessary.",
                details={"duration_ms": trace.duration_ms},
            )

        # Diagnose primary failure
        primary_error = trace.errors[-1] if trace.errors else None
        err_msg = primary_error.message if primary_error else (trace.error or "Unknown failure")
        err_code = primary_error.error_code if primary_error else "ERR_TASK_FAILED"
        comp = primary_error.component if primary_error else ComponentType.AGENT_CORE

        root_cause, failed_action, suggested_fix = self._diagnose_failure(err_code, err_msg, trace)

        report = DiagnosticReport(
            trace_id=trace.trace_id,
            error_code=err_code,
            component=comp,
            root_cause=root_cause,
            failed_action=failed_action,
            suggested_fix=suggested_fix,
            details={
                "error_message": err_msg,
                "tools_used": trace.tools_used,
                "verification_result": trace.verification_result,
                "duration_ms": trace.duration_ms,
            },
        )

        logger.info(
            "diagnostic_report_generated",
            trace_id=str(trace_id),
            error_code=err_code,
            root_cause=root_cause,
        )
        return report

    def _diagnose_failure(self, error_code: str, msg: str, trace: TraceRecord) -> tuple[str, str, str]:
        """Classify failure root cause and provide explicit remediation recommendation."""
        msg_low = msg.lower()

        # 1. Permission Denials
        if "permission" in error_code.lower() or "denied" in msg_low:
            return (
                "Permission Gate blocked tool execution: operation requires interactive user confirmation or elevated privilege.",
                trace.tools_used[-1] if trace.tools_used else "Tool execution",
                "Request explicit user authorization over WebSocket or configure auto-grant in session settings.",
            )

        # 2. Timeouts
        if "timeout" in error_code.lower() or "timeout" in msg_low:
            return (
                "Operation exceeded deadline limit during external communication or heavy local processing.",
                trace.tools_used[-1] if trace.tools_used else "Network/Task execution",
                "Increase timeout threshold in settings or decompose the goal into smaller asynchronous sub-tasks.",
            )

        # 3. Retrieval / RAG Failures
        if "rag" in error_code.lower() or "retriev" in msg_low:
            return (
                "RAG / Knowledge retrieval returned insufficient or empty context chunks.",
                "RAG semantic search",
                "Re-index project files or use DuckDuckGo Web Research as external fallback context.",
            )

        # 4. Model Failures / Hallucination / Rate Limits
        if "model" in error_code.lower() or "rate limit" in msg_low:
            return (
                "Model Provider rate limit reached or model response failed schema validation.",
                f"Model Gateway ({trace.model or 'default'})",
                "Switch to local Qwen model fallback or apply exponential backoff.",
            )

        # 5. Generic Tool Failures
        failed_tool = trace.tools_used[-1] if trace.tools_used else "General action"
        return (
            f"Execution failure during {failed_tool}: {msg}",
            failed_tool,
            "Check tool input parameters, verify target path/file existence, and ensure environment dependencies are installed.",
        )
