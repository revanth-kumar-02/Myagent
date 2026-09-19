"""
observability.replay — Read-Only Agent Execution Replay Engine (V14).

Reconstructs immutable step-by-step playback snapshots of historical agent executions.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from observability.tracer import AgentTracer
from observability.types import EventType, ReplaySnapshot, ReplayStep, TraceRecord

logger = structlog.get_logger(__name__)


class AgentReplayEngine:
    """
    Assembles historical traces into structured, read-only replay snapshots.
    """

    def __init__(self, tracer: AgentTracer) -> None:
        self.tracer = tracer

    def generate_replay(self, trace_id: uuid.UUID) -> ReplaySnapshot | None:
        """
        Generate an immutable ReplaySnapshot for the specified trace.
        """
        trace = self.tracer.get_trace(trace_id)
        if trace is None:
            return None

        steps: list[ReplayStep] = []
        user_request = str(trace.metadata.get("message", trace.metadata.get("prompt", "User Request")))
        plan_summary = ""
        context_summary = trace.retrieved_context_summary or ""
        final_response = str(trace.metadata.get("final_response", ""))

        step_idx = 0

        # Step 0: User Request
        steps.append(
            ReplayStep(
                step_index=step_idx,
                step_type="request",
                label="Incoming User Request",
                input_payload={"message": user_request},
                timestamp=trace.created_at,
            )
        )
        step_idx += 1

        # Process trace events into sequential replay steps
        for ev in trace.events:
            if ev.event_type == EventType.PLANNING_STARTED:
                plan_summary = str(ev.payload.get("plan_summary", "Plan generated"))
                steps.append(
                    ReplayStep(
                        step_index=step_idx,
                        step_type="plan",
                        label="Task Planning",
                        input_payload=ev.payload,
                        duration_ms=ev.duration_ms,
                        timestamp=ev.timestamp,
                    )
                )
                step_idx += 1

            elif ev.event_type == EventType.CONTEXT_RETRIEVED:
                context_summary = str(ev.payload.get("context_summary", "Retrieved sources"))
                steps.append(
                    ReplayStep(
                        step_index=step_idx,
                        step_type="context",
                        label="Context Retrieval",
                        output_payload=ev.payload,
                        duration_ms=ev.duration_ms,
                        timestamp=ev.timestamp,
                    )
                )
                step_idx += 1

            elif ev.event_type in (EventType.TOOL_STARTED, EventType.TOOL_COMPLETED):
                tool_name = str(ev.payload.get("tool_name", "tool"))
                steps.append(
                    ReplayStep(
                        step_index=step_idx,
                        step_type="tool_call",
                        label=f"Tool Execution: {tool_name}",
                        tool_name=tool_name,
                        input_payload=ev.payload.get("params"),
                        output_payload=ev.payload.get("output"),
                        duration_ms=ev.duration_ms,
                        status=ev.status,
                        timestamp=ev.timestamp,
                    )
                )
                step_idx += 1

            elif ev.event_type == EventType.VERIFICATION_COMPLETED:
                steps.append(
                    ReplayStep(
                        step_index=step_idx,
                        step_type="verification",
                        label="Result Verification",
                        output_payload=ev.payload,
                        verification_verdict=str(ev.payload.get("verdict", "pass")),
                        duration_ms=ev.duration_ms,
                        timestamp=ev.timestamp,
                    )
                )
                step_idx += 1

        # Final Step: Agent Response
        steps.append(
            ReplayStep(
                step_index=step_idx,
                step_type="response",
                label="Final Response",
                output_payload={"response": final_response, "status": trace.final_status},
                status=trace.final_status,
                timestamp=trace.completed_at or trace.created_at,
            )
        )

        snapshot = ReplaySnapshot(
            trace_id=trace.trace_id,
            task_id=trace.task_id,
            user_request=user_request,
            plan_summary=plan_summary,
            context_summary=context_summary,
            steps=steps,
            final_response=final_response,
            duration_ms=trace.duration_ms,
            status=trace.final_status,
            is_read_only=True,
            created_at=trace.created_at,
        )

        logger.info(
            "replay_snapshot_generated",
            trace_id=str(trace_id),
            steps_count=len(steps),
            duration_ms=trace.duration_ms,
        )
        return snapshot
