"""
vision.workflows.conditions — Visual Condition Evaluator (V20)

Evaluates pre-conditions and branching rules against real-time screen analysis.
"""

from __future__ import annotations

import structlog

from vision.types import UIElementType, VisualAnalysisResult
from vision.workflows.types import ConditionType, StepExecutionRecord, VisualStepCondition

logger = structlog.get_logger(__name__)


class VisualConditionEvaluator:
    """
    Evaluates visual and execution conditions for workflow branching and guards.
    """

    def evaluate(
        self,
        condition: VisualStepCondition,
        analysis: VisualAnalysisResult,
        previous_step_record: StepExecutionRecord | None = None,
    ) -> bool:
        """
        Evaluate a single condition against visual analysis and previous step state.
        """
        cond_type = condition.condition_type
        target_label = (condition.target_label or "").strip().lower()
        expected_text = (condition.expected_text or "").strip().lower()

        raw_result = False

        if cond_type == ConditionType.ELEMENT_EXISTS:
            if target_label:
                raw_result = any(target_label in el.label.lower() for el in analysis.detected_elements)
            else:
                raw_result = len(analysis.detected_elements) > 0

        elif cond_type == ConditionType.TEXT_APPEARS:
            if expected_text:
                text_corpus = " ".join(analysis.detected_text).lower() + " " + analysis.summary.lower()
                raw_result = expected_text in text_corpus
            else:
                raw_result = len(analysis.detected_text) > 0

        elif cond_type == ConditionType.DIALOG_APPEARS:
            has_dialog_element = any(el.element_type == UIElementType.DIALOG for el in analysis.detected_elements)
            has_error_msg = len(analysis.error_messages) > 0
            raw_result = has_dialog_element or has_error_msg

        elif cond_type == ConditionType.SCREEN_STATE_MATCHES:
            target_str = expected_text or target_label
            win_str = (analysis.active_window or "").lower()
            summary_str = analysis.summary.lower()
            raw_result = target_str in win_str or target_str in summary_str

        elif cond_type == ConditionType.PREVIOUS_ACTION_SUCCEEDED:
            if previous_step_record:
                raw_result = previous_step_record.executed and previous_step_record.error_message is None
            else:
                raw_result = True

        final_result = not raw_result if condition.negate else raw_result
        logger.debug(
            "visual_condition_evaluated",
            condition_type=cond_type.value,
            raw_result=raw_result,
            negate=condition.negate,
            final_result=final_result,
        )
        return final_result
