"""
vision.context — Visual Context Builder (V19)

Assembles bounded visual context summaries for Agent Reasoning,
Planning, and Context Resolver integration.
"""

from __future__ import annotations

from typing import Sequence

import structlog

from vision.types import ScreenContext, UIElement, VisualAnalysisResult

logger = structlog.get_logger(__name__)


class VisualContextBuilder:
    """
    Builds structured, prompt-ready visual context from visual analysis results.
    """

    def build_elements_summary(self, elements: Sequence[UIElement], max_elements: int = 20) -> str:
        """Format detected UI elements into a compact list with coordinates and roles."""
        if not elements:
            return "No distinct UI elements detected."

        lines = []
        for el in list(elements)[:max_elements]:
            clickable_tag = " [clickable]" if el.is_clickable else ""
            lines.append(
                f"- [{el.element_type.value.upper()}] '{el.label}' at ({el.bounding_box.x}, {el.bounding_box.y}, "
                f"w:{el.bounding_box.width}, h:{el.bounding_box.height}){clickable_tag}"
            )

        if len(elements) > max_elements:
            lines.append(f"... and {len(elements) - max_elements} more elements.")

        return "\n".join(lines)

    def build_context(
        self,
        analysis: VisualAnalysisResult,
        screenshot_path: str,
    ) -> ScreenContext:
        """
        Assemble bounded ScreenContext object.
        """
        elem_summary = self.build_elements_summary(analysis.detected_elements)
        win_info = analysis.active_window or "Desktop / Active Window"

        return ScreenContext(
            summary=analysis.summary,
            elements_summary=elem_summary,
            active_window_info=win_info,
            screenshot_path=screenshot_path,
            confidence=analysis.confidence,
        )
