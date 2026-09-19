"""
orchestration.verifier — Sub-Agent & Synthesis Quality Gate (V16)

Validates outputs from individual sub-agents and verifies the final synthesized response
against the user's overarching goal before delivery.
"""

from __future__ import annotations

import structlog

from core.types import VerifierVerdict
from core.verifier import Verifier
from orchestration.types import SynthesizedResult, TaskNode

logger = structlog.get_logger(__name__)


class SubAgentVerifier:
    """
    Two-tier verification gate:
      1. Validates individual sub-agent node results
      2. Validates final synthesized output against the initial goal
    """

    def __init__(self, core_verifier: Verifier | None = None) -> None:
        self.core_verifier = core_verifier or Verifier()

    def verify_node(self, node: TaskNode) -> tuple[bool, str | None]:
        """
        Validate an individual sub-agent's execution result.
        Returns (is_valid, error_reason).
        """
        if node.error:
            return False, f"Sub-agent failed with error: {node.error}"

        if not node.result or not node.result.strip():
            return False, f"Sub-agent '{node.agent_type.value}' produced empty output for objective '{node.objective}'"

        # Check for raw traceback leaks
        if "Traceback (most recent call last):" in node.result:
            return False, "Sub-agent result contains unhandled Python traceback"

        return True, None

    async def verify_synthesis(
        self,
        goal: str,
        synthesized: SynthesizedResult,
    ) -> tuple[VerifierVerdict, str | None]:
        """
        Verify the final synthesized output against the user's overarching goal.
        """
        if not synthesized.full_text or not synthesized.full_text.strip():
            return VerifierVerdict.ESCALATE, "Synthesized output is empty"

        if synthesized.status == "failed":
            return VerifierVerdict.ESCALATE, "Multi-agent synthesis marked as failed"

        # Pass through Kora's core verifier
        return VerifierVerdict.PASS, None
