"""
vision.detector — Structured UI Element Detector (V19)

Extracts and parses UI elements (buttons, inputs, menus, links, dialogs,
icons, checkboxes, tables) with coordinates and confidence scores.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog

from vision.types import BoundingBox, UIElement, UIElementType

logger = structlog.get_logger(__name__)


class UIElementDetector:
    """
    Parses and structures detected UI elements from visual model outputs or heuristics.
    """

    def parse_elements(
        self,
        raw_elements: list[dict[str, Any]],
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> list[UIElement]:
        """
        Convert raw dictionary representations into validated UIElement objects.
        """
        results: list[UIElement] = []

        for idx, item in enumerate(raw_elements):
            elem_id = item.get("id") or item.get("element_id") or f"elem_{uuid.uuid4().hex[:6]}"
            raw_type = item.get("type") or item.get("element_type", "custom")
            label = str(item.get("label") or item.get("text") or item.get("name", "")).strip()

            try:
                elem_type = UIElementType(raw_type.lower())
            except ValueError:
                elem_type = UIElementType.CUSTOM

            # Coordinates handling
            bbox_data = item.get("bbox") or item.get("bounding_box") or {}
            x = int(bbox_data.get("x", item.get("x", 0)))
            y = int(bbox_data.get("y", item.get("y", 0)))
            w = int(bbox_data.get("width", bbox_data.get("w", item.get("width", item.get("w", 50)))))
            h = int(bbox_data.get("height", bbox_data.get("h", item.get("height", item.get("h", 30)))))

            norm_x = float(bbox_data.get("normalized_x", x / max(screen_width, 1)))
            norm_y = float(bbox_data.get("normalized_y", y / max(screen_height, 1)))
            norm_w = float(bbox_data.get("normalized_width", w / max(screen_width, 1)))
            norm_h = float(bbox_data.get("normalized_height", h / max(screen_height, 1)))

            bbox = BoundingBox(
                x=x,
                y=y,
                width=w,
                height=h,
                normalized_x=norm_x,
                normalized_y=norm_y,
                normalized_width=norm_w,
                normalized_height=norm_h,
            )

            confidence = float(item.get("confidence", 1.0))
            is_clickable = bool(item.get("is_clickable", elem_type in {
                UIElementType.BUTTON,
                UIElementType.LINK,
                UIElementType.MENU,
                UIElementType.CHECKBOX,
                UIElementType.ICON,
            }))
            is_focused = bool(item.get("is_focused", False))
            value = item.get("value")

            results.append(
                UIElement(
                    element_id=elem_id,
                    element_type=elem_type,
                    label=label,
                    bounding_box=bbox,
                    confidence=confidence,
                    is_clickable=is_clickable,
                    is_focused=is_focused,
                    value=str(value) if value is not None else None,
                    attributes=item.get("attributes", {}),
                )
            )

        return results

    def find_by_label(
        self,
        elements: list[UIElement],
        query: str,
        exact: bool = False,
    ) -> list[UIElement]:
        """Filter detected elements by label matching."""
        q = query.strip().lower()
        if exact:
            return [el for el in elements if el.label.lower() == q]
        return [el for el in elements if q in el.label.lower()]

    def find_by_type(
        self,
        elements: list[UIElement],
        elem_type: UIElementType,
    ) -> list[UIElement]:
        """Filter detected elements by UI type."""
        return [el for el in elements if el.element_type == elem_type]

    def find_clickable(self, elements: list[UIElement]) -> list[UIElement]:
        """Return all clickable elements."""
        return [el for el in elements if el.is_clickable]
