"""
core.verifier — Execution Result Verifier (V7)

Responsibilities:
  - Evaluate the quality and validity of an ExecutorResult
  - Compare actual outputs against expected step criteria
  - Return one of three verdicts:
      PASS     → Output is verified and valid, continue to next step or finalize
      RETRY    → Result failed or has poor quality, retry step (max 2 retries)
      ESCALATE → Cannot improve via retry, trigger replanning or notify user
"""

from __future__ import annotations

import structlog

from core.types import ActionType, ExecutorResult, VerifierVerdict

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 2

# Common refusal / unhelpful phrases indicating poor generation
_REFUSAL_PHRASES = [
    "i cannot answer this",
    "as an ai language model",
    "i do not have access to real-time",
]


class Verifier:
    """
    Quality gate validating execution outputs against plan expectations.
    """

    async def check(
        self,
        result: ExecutorResult,
        attempt: int = 0,
    ) -> VerifierVerdict:
        """
        Evaluate result quality and return a VerifierVerdict.
        """
        # 1. Check max retries
        if attempt >= _MAX_RETRIES:
            logger.warning("verifier_max_retries_exceeded_escalating", attempt=attempt)
            return VerifierVerdict.ESCALATE

        # 2. Check execution failure flag or error
        if not result.success or result.error:
            logger.debug("verifier_step_unsuccessful", error=result.error, attempt=attempt)
            return VerifierVerdict.RETRY

        # 3. Check for empty content
        content = result.content.strip()
        if not content:
            logger.debug("verifier_empty_content_retry", attempt=attempt)
            return VerifierVerdict.RETRY

        # 4. Action-specific quality checks
        match result.step.action_type:
            case ActionType.MODEL_GENERATE:
                # Check for refusal phrases
                lower_content = content.lower()
                if any(phrase in lower_content for phrase in _REFUSAL_PHRASES):
                    logger.warning("verifier_model_refusal_detected", attempt=attempt)
                    return VerifierVerdict.RETRY

            case ActionType.TOOL_CALL:
                # Check for explicit failure strings in output
                if "error:" in content.lower() or "traceback" in content.lower():
                    if "failed" in content.lower() or "exception" in content.lower():
                        return VerifierVerdict.RETRY

            case ActionType.RAG_QUERY:
                # If RAG returned explicit empty indication
                if "no relevant project knowledge" in content.lower():
                    pass  # Pass through so planner can proceed or fall back

        logger.debug("verifier_passed", step=result.step.label)
        return VerifierVerdict.PASS
