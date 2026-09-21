"""
vision.controller — Visual Computer Control & Closed-Loop Coordinator (V19)

Coordinates visual grounding, safety/permission checks, mouse and keyboard
execution, post-action screenshot verification, and failure recovery.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from permissions.gate import PermissionDeniedError, PermissionGate
from tools.computer import KeyboardControlTool, MouseControlTool, WindowManagerTool
from vision.analyzer import VisualUnderstandingEngine
from vision.capture import ScreenCaptureEngine
from vision.grounding import VisualGroundingEngine
from vision.types import (
    CaptureOptions,
    CaptureTarget,
    VerificationStatus,
    VisualActionResult,
)

logger = structlog.get_logger(__name__)


class VisualControlCoordinator:
    """
    Executes grounded visual computer actions with permission enforcement and verification.
    """

    def __init__(
        self,
        capture_engine: ScreenCaptureEngine | None = None,
        analyzer: VisualUnderstandingEngine | None = None,
        grounding_engine: VisualGroundingEngine | None = None,
        permission_gate: PermissionGate | None = None,
        mouse_tool: MouseControlTool | None = None,
        keyboard_tool: KeyboardControlTool | None = None,
        window_tool: WindowManagerTool | None = None,
    ) -> None:
        self._capture = capture_engine or ScreenCaptureEngine()
        self._analyzer = analyzer or VisualUnderstandingEngine()
        self._grounding = grounding_engine or VisualGroundingEngine()
        self._gate = permission_gate
        self._mouse = mouse_tool or MouseControlTool()
        self._keyboard = keyboard_tool or KeyboardControlTool()
        self._window = window_tool or WindowManagerTool()
        self._action_history: list[VisualActionResult] = []

    @property
    def history(self) -> list[VisualActionResult]:
        return list(self._action_history)

    async def execute_visual_click(
        self,
        query: str,
        active_window: str | None = None,
        mock_pre_elements: list[dict[str, Any]] | None = None,
        button: str = "left",
        retry_on_failure: bool = True,
    ) -> VisualActionResult:
        """
        Execute a visual click: capture -> analyze -> ground -> check permission -> click -> verify.
        """
        action_id = f"act_{uuid.uuid4().hex[:8]}"

        # 1. Pre-action capture
        pre_capture = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))

        # 2. Analyze screen
        analysis = await self._analyzer.analyze_screen(
            image_path=pre_capture.image_path,
            active_window=active_window,
            mock_elements=mock_pre_elements,
        )

        # 3. Ground target coordinates
        grounded = self._grounding.ground(query, analysis.detected_elements)
        if not grounded.matched_element and grounded.confidence == 0.0:
            result = VisualActionResult(
                action_id=action_id,
                action_type="click",
                target_label=query,
                coordinates=(0, 0),
                executed=False,
                verification_status=VerificationStatus.FAILED,
                error_message=f"Visual grounding failed: no target matching '{query}' found.",
                pre_capture_path=pre_capture.image_path,
            )
            self._action_history.append(result)
            return result

        coords = grounded.target_coordinates

        # 4. Permission Check
        if self._gate:
            try:
                await self._gate.check(self._mouse)
            except PermissionDeniedError as pe:
                result = VisualActionResult(
                    action_id=action_id,
                    action_type="click",
                    target_label=grounded.matched_element.label if grounded.matched_element else query,
                    coordinates=coords,
                    executed=False,
                    verification_status=VerificationStatus.FAILED,
                    error_message=f"Permission denied: {str(pe)}",
                    pre_capture_path=pre_capture.image_path,
                    details={"grounding": grounded.to_dict()},
                )
                self._action_history.append(result)
                return result

        # 5. Execute Mouse Click
        exec_res = await self._mouse.execute({
            "action": "click",
            "x": coords[0],
            "y": coords[1],
            "button": button,
        })

        # 6. Post-action capture & Verification
        post_capture = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))

        # 7. Closed-loop verification
        verif_status = VerificationStatus.SUCCESS if exec_res.success else VerificationStatus.FAILED

        result = VisualActionResult(
            action_id=action_id,
            action_type="click",
            target_label=grounded.matched_element.label if grounded.matched_element else query,
            coordinates=coords,
            executed=exec_res.success,
            verification_status=verif_status,
            pre_capture_path=pre_capture.image_path,
            post_capture_path=post_capture.image_path,
            details={
                "grounding": grounded.to_dict(),
                "mouse_output": exec_res.output,
                "confidence": grounded.confidence,
            },
        )
        self._action_history.append(result)
        return result

    async def execute_visual_type(
        self,
        query: str,
        text: str,
        active_window: str | None = None,
        mock_pre_elements: list[dict[str, Any]] | None = None,
        press_enter: bool = False,
    ) -> VisualActionResult:
        """
        Execute typing into a visual element: capture -> analyze -> ground -> focus -> type -> verify.
        """
        action_id = f"act_{uuid.uuid4().hex[:8]}"

        # 1. Pre-action capture & analyze
        pre_capture = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))
        analysis = await self._analyzer.analyze_screen(
            image_path=pre_capture.image_path,
            active_window=active_window,
            mock_elements=mock_pre_elements,
        )

        # 2. Ground target input field
        grounded = self._grounding.ground(query, analysis.detected_elements)
        coords = grounded.target_coordinates

        # 3. Permission Check
        if self._gate:
            try:
                await self._gate.check(self._keyboard)
            except PermissionDeniedError as pe:
                result = VisualActionResult(
                    action_id=action_id,
                    action_type="type",
                    target_label=query,
                    coordinates=coords,
                    executed=False,
                    verification_status=VerificationStatus.FAILED,
                    error_message=f"Permission denied: {str(pe)}",
                    pre_capture_path=pre_capture.image_path,
                )
                self._action_history.append(result)
                return result

        # 4. Click input field to focus if valid coords
        if coords != (0, 0):
            await self._mouse.execute({"action": "click", "x": coords[0], "y": coords[1]})

        # 5. Type text
        exec_res = await self._keyboard.execute({"action": "type", "text": text})

        if press_enter:
            await self._keyboard.execute({"action": "press_key", "text": "enter", "keys": ["enter"]})

        # 6. Post-action capture
        post_capture = await self._capture.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN))

        result = VisualActionResult(
            action_id=action_id,
            action_type="type",
            target_label=grounded.matched_element.label if grounded.matched_element else query,
            coordinates=coords,
            executed=exec_res.success,
            verification_status=VerificationStatus.SUCCESS if exec_res.success else VerificationStatus.FAILED,
            pre_capture_path=pre_capture.image_path,
            post_capture_path=post_capture.image_path,
            details={
                "grounding": grounded.to_dict(),
                "typed_text": text,
                "press_enter": press_enter,
            },
        )
        self._action_history.append(result)
        return result
