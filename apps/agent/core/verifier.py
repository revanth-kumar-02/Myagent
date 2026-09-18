"""
core.verifier — Verifier

Responsibilities:
  - Evaluate the quality of an ExecutorResult
  - Return one of three verdicts:
      PASS     → context is good, continue to next step or finalize
      RETRY    → result is poor quality, ask Executor to retry (max 2 retries)
      ESCALATE → cannot improve; use a stronger model or report to user

The verifier uses lightweight heuristics and optionally a model call.
It does NOT alter results — it only classifies them.
"""

from __future__ import annotations

import structlog

from core.types import ExecutorResult, VerifierVerdict

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 2


class Verifier:
    """
    Lightweight result quality gate.

    For RAG results: checks chunk count and minimum relevance score.
    For tool results: checks success flag and non-empty output.
    For model results: checks non-empty, non-refusal output.
    """

    async def check(
        self,
        result: ExecutorResult,
        attempt: int = 0,
    ) -> VerifierVerdict:
        """
        Evaluate result quality.

        attempt: number of retries already performed for this step (0-indexed).
        Returns ESCALATE automatically when attempt >= _MAX_RETRIES.
        """
        if attempt >= _MAX_RETRIES:
            return VerifierVerdict.ESCALATE

        if not result.success:
            return VerifierVerdict.RETRY

        raise NotImplementedError  # TODO: implement quality heuristics in feature phase
