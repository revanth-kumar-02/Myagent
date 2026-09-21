"""
vision.grounding — Visual Coordinate & Element Grounding Engine (V19)

Maps natural language instructions (e.g. 'click Settings button') to
detected visual elements, computing exact center click coordinates without
relying solely on brittle fixed coordinates.
"""

from __future__ import annotations

import re
from typing import Sequence

import structlog

from vision.types import UIElement, UIElementType, VisualGroundingTarget

logger = structlog.get_logger(__name__)


class VisualGroundingEngine:
    """
    Grounds natural language intent into screen elements and coordinate targets.
    """

    def _extract_intent_tokens(self, query: str) -> tuple[str, UIElementType | None]:
        """Extract clean target label text and optional element type hint."""
        clean_q = query.lower().strip()

        # Remove common command prefixes
        clean_q = re.sub(r"^(?:click|press|tap|select|focus|type\s+in|choose)\s+(?:on\s+)?(?:the\s+)?", "", clean_q)

        type_hint: UIElementType | None = None
        if "button" in clean_q:
            type_hint = UIElementType.BUTTON
            clean_q = re.sub(r"\s+button\b", "", clean_q).strip()
        elif "input" in clean_q or "field" in clean_q or "box" in clean_q:
            type_hint = UIElementType.INPUT_FIELD
            clean_q = re.sub(r"\s+(?:input|field|box)\b", "", clean_q).strip()
        elif "link" in clean_q:
            type_hint = UIElementType.LINK
            clean_q = re.sub(r"\s+link\b", "", clean_q).strip()
        elif "menu" in clean_q:
            type_hint = UIElementType.MENU
            clean_q = re.sub(r"\s+menu\b", "", clean_q).strip()
        elif "checkbox" in clean_q:
            type_hint = UIElementType.CHECKBOX
            clean_q = re.sub(r"\s+checkbox\b", "", clean_q).strip()
        elif "icon" in clean_q:
            type_hint = UIElementType.ICON
            clean_q = re.sub(r"\s+icon\b", "", clean_q).strip()

        return clean_q.strip(), type_hint

    def ground(
        self,
        query: str,
        elements: Sequence[UIElement],
        fallback_coordinates: tuple[int, int] | None = None,
    ) -> VisualGroundingTarget:
        """
        Match a natural language target query against a list of detected UI elements.
        """
        if not elements:
            if fallback_coordinates:
                return VisualGroundingTarget(
                    query=query,
                    matched_element=None,
                    target_coordinates=fallback_coordinates,
                    confidence=0.5,
                    rationale="No UI elements detected. Using provided fallback coordinates.",
                )
            return VisualGroundingTarget(
                query=query,
                matched_element=None,
                target_coordinates=(0, 0),
                confidence=0.0,
                rationale="No UI elements available to ground the query.",
            )

        target_label, type_hint = self._extract_intent_tokens(query)

        best_element: UIElement | None = None
        best_score = -1.0
        best_rationale = ""

        for el in elements:
            score = 0.0
            el_label_clean = el.label.lower().strip()

            # Exact label match
            if el_label_clean == target_label:
                score += 1.0
            # Substring match
            elif target_label and target_label in el_label_clean:
                score += 0.75
            elif el_label_clean and el_label_clean in target_label:
                score += 0.65

            # Element type match bonus
            if type_hint and el.element_type == type_hint:
                score += 0.25
            elif el.is_clickable:
                score += 0.1

            # Element confidence factor
            score *= el.confidence

            if score > best_score:
                best_score = score
                best_element = el
                best_rationale = f"Matched element '{el.label}' ({el.element_type.value}) with score {round(score, 2)}."

        if best_element and best_score > 0.3:
            coords = best_element.bounding_box.center
            logger.info(
                "visual_grounding_success",
                query=query,
                matched_label=best_element.label,
                coordinates=coords,
                confidence=best_score,
            )
            return VisualGroundingTarget(
                query=query,
                matched_element=best_element,
                target_coordinates=coords,
                confidence=min(1.0, best_score),
                rationale=best_rationale,
            )

        # Fallback if no strong match
        if fallback_coordinates:
            return VisualGroundingTarget(
                query=query,
                matched_element=None,
                target_coordinates=fallback_coordinates,
                confidence=0.3,
                rationale=f"Could not find strong match for '{query}'. Used fallback coordinates.",
            )

        return VisualGroundingTarget(
            query=query,
            matched_element=None,
            target_coordinates=(0, 0),
            confidence=0.0,
            rationale=f"No matching visual element found for '{query}'.",
        )
