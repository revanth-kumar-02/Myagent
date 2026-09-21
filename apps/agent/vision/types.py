"""
vision.types — Domain Types for Computer Vision & Screen Intelligence (V19)

Defines bounding boxes, UI element abstractions, capture options,
analysis results, visual grounding targets, and verification statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class UIElementType(str, Enum):
    """Categorization of detected user interface elements."""
    BUTTON = "button"
    INPUT_FIELD = "input_field"
    TEXT = "text"
    MENU = "menu"
    LINK = "link"
    DIALOG = "dialog"
    ICON = "icon"
    CHECKBOX = "checkbox"
    TABLE = "table"
    WINDOW = "window"
    CUSTOM = "custom"


class CaptureTarget(str, Enum):
    """Screen capture scope."""
    FULL_SCREEN = "full_screen"
    MONITOR = "monitor"
    WINDOW = "window"
    REGION = "region"


class VerificationStatus(str, Enum):
    """Result of post-action visual verification."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box coordinates for a visual element."""
    x: int
    y: int
    width: int
    height: int
    normalized_x: float = 0.0
    normalized_y: float = 0.0
    normalized_width: float = 0.0
    normalized_height: float = 0.0

    @property
    def center(self) -> tuple[int, int]:
        """Return the integer (center_x, center_y) pixel coordinates."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center": list(self.center),
            "normalized_x": round(self.normalized_x, 4),
            "normalized_y": round(self.normalized_y, 4),
            "normalized_width": round(self.normalized_width, 4),
            "normalized_height": round(self.normalized_height, 4),
        }


@dataclass
class UIElement:
    """Structured detected user interface element."""
    element_id: str
    element_type: UIElementType
    label: str
    bounding_box: BoundingBox
    confidence: float = 1.0
    is_clickable: bool = True
    is_focused: bool = False
    value: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value,
            "label": self.label,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "is_clickable": self.is_clickable,
            "is_focused": self.is_focused,
            "value": self.value,
            "attributes": self.attributes,
        }


@dataclass
class CaptureOptions:
    """Configuration options for a screen capture operation."""
    target: CaptureTarget = CaptureTarget.FULL_SCREEN
    monitor_index: int | None = None
    window_id: str | None = None
    region: tuple[int, int, int, int] | None = None
    output_path: str | None = None
    ephemeral: bool = True


@dataclass
class ScreenCaptureResult:
    """Result of capturing a screenshot."""
    capture_id: str
    image_path: str
    width: int
    height: int
    target: CaptureTarget
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    monitor_index: int | None = None
    window_id: str | None = None
    region: tuple[int, int, int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_ephemeral: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "image_path": self.image_path,
            "width": self.width,
            "height": self.height,
            "target": self.target.value,
            "timestamp": self.timestamp.isoformat(),
            "monitor_index": self.monitor_index,
            "window_id": self.window_id,
            "region": list(self.region) if self.region else None,
            "metadata": self.metadata,
            "is_ephemeral": self.is_ephemeral,
        }


@dataclass
class VisualAnalysisResult:
    """Rich semantic analysis of a screenshot or image."""
    analysis_id: str
    summary: str
    description: str
    detected_elements: list[UIElement] = field(default_factory=list)
    detected_text: list[str] = field(default_factory=list)
    active_window: str | None = None
    error_messages: list[str] = field(default_factory=list)
    confidence: float = 1.0
    raw_response: str = ""
    model_used: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "summary": self.summary,
            "description": self.description,
            "detected_elements": [el.to_dict() for el in self.detected_elements],
            "detected_text": self.detected_text,
            "active_window": self.active_window,
            "error_messages": self.error_messages,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VisualGroundingTarget:
    """Mapping from natural language intent to resolved coordinates."""
    query: str
    matched_element: UIElement | None
    target_coordinates: tuple[int, int]
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "matched_element": self.matched_element.to_dict() if self.matched_element else None,
            "target_coordinates": list(self.target_coordinates),
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass
class ScreenContext:
    """Visual context package ready for Agent reasoning."""
    summary: str
    elements_summary: str
    active_window_info: str
    screenshot_path: str
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format_for_prompt(self) -> str:
        """Format bounded visual context for agent prompt inclusion."""
        parts = [
            f"[Visual Screen Context ({self.timestamp.strftime('%H:%M:%S UTC')})]",
            f"Active Window: {self.active_window_info}",
            f"Summary: {self.summary}",
            f"Detected UI Elements:\n{self.elements_summary}",
        ]
        return "\n".join(parts)


@dataclass
class VisualActionResult:
    """Result of an executed visual computer control action."""
    action_id: str
    action_type: str
    target_label: str
    coordinates: tuple[int, int]
    executed: bool
    verification_status: VerificationStatus
    error_message: str | None = None
    pre_capture_path: str | None = None
    post_capture_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_label": self.target_label,
            "coordinates": list(self.coordinates),
            "executed": self.executed,
            "verification_status": self.verification_status.value,
            "error_message": self.error_message,
            "pre_capture_path": self.pre_capture_path,
            "post_capture_path": self.post_capture_path,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }
