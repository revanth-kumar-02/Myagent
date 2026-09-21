"""
tests.agent.test_vision_v19 — Test Suite for Computer Vision & Screen Intelligence (V19)

Verifies:
- Multi-monitor, window, and region capture across platform adapters
- Dynamic vision model resolution without hardcoded model IDs
- UI element detection with structured coordinates and confidence
- Visual grounding of natural language intent to click coordinates
- Closed-loop visual computer control with PermissionGate enforcement
- Post-action verification and safe error handling
- Bounded visual context assembly
- Privacy and credential masking protections
"""

import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.model_router import ModelRouter
from models.registry import ModelRegistry
from permissions.gate import PermissionGate, PermissionDeniedError
from permissions.types import PermissionGrant
from tools.computer import KeyboardControlTool, MouseControlTool, ScreenCaptureTool, WindowManagerTool
from tools.platforms.linux import LinuxAdapter
from tools.platforms.macos import MacOSAdapter
from tools.platforms.windows import WindowsAdapter
from vision import (
    BoundingBox,
    CaptureOptions,
    CaptureTarget,
    ScreenCaptureEngine,
    ScreenCaptureResult,
    UIElement,
    UIElementDetector,
    UIElementType,
    VerificationStatus,
    VisualActionResult,
    VisualAnalysisResult,
    VisualContextBuilder,
    VisualControlCoordinator,
    VisualGroundingEngine,
    VisualGroundingTarget,
    VisualUnderstandingEngine,
)


@pytest.fixture
def mock_model_registry(tmp_path: pathlib.Path) -> ModelRegistry:
    yaml_content = """
models:
  gemma-vision:
    provider: huggingface
    model_id: "google/gemma-3-12b-it"
    capabilities:
      - vision
    context_window: 131072
"""
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml_content)
    return ModelRegistry.load(reg_file)


@pytest.mark.asyncio
async def test_screen_capture_engine_options_and_targets(tmp_path: pathlib.Path):
    """Test full screen, monitor, window, and region capture with ephemeral lifecycle."""
    adapter = LinuxAdapter()
    engine = ScreenCaptureEngine(adapter=adapter, base_temp_dir=str(tmp_path))

    # 1. Full screen capture
    res_full = await engine.capture(CaptureOptions(target=CaptureTarget.FULL_SCREEN, ephemeral=True))
    assert res_full.target == CaptureTarget.FULL_SCREEN
    assert res_full.width == 1920
    assert res_full.height == 1080
    assert res_full.is_ephemeral is True

    # 2. Region capture
    res_region = await engine.capture(
        CaptureOptions(
            target=CaptureTarget.REGION,
            region=(100, 150, 400, 300),
            ephemeral=True,
        )
    )
    assert res_region.target == CaptureTarget.REGION
    assert res_region.region == (100, 150, 400, 300)
    assert res_region.width == 400
    assert res_region.height == 300

    # 3. Monitor capture
    res_mon = await engine.capture(CaptureOptions(target=CaptureTarget.MONITOR, monitor_index=0))
    assert res_mon.monitor_index == 0

    # 4. Ephemeral cleanup
    cleaned = engine.cleanup_all()
    assert isinstance(cleaned, int)


@pytest.mark.asyncio
async def test_platform_adapters_capture_abstractions():
    """Verify Linux, Windows, and macOS platform adapters return monitors and handle capture."""
    adapters = [LinuxAdapter(), WindowsAdapter(), MacOSAdapter()]

    for adapter in adapters:
        monitors = await adapter.get_monitors()
        assert isinstance(monitors, list)
        assert len(monitors) >= 1
        assert "width" in monitors[0]
        assert "height" in monitors[0]

        shot_path = await adapter.capture_screen(
            output_path="/tmp/test_shot.png",
            monitor_index=0,
            region=(10, 10, 200, 200),
        )
        assert "/tmp/test_shot.png" in shot_path or "test_shot.png" in shot_path


@pytest.mark.asyncio
async def test_vision_model_resolution_no_hardcoding(mock_model_registry: ModelRegistry):
    """Ensure visual model is dynamically retrieved via router/registry without hardcoded IDs."""
    router = ModelRouter(mock_model_registry)
    analyzer = VisualUnderstandingEngine(router=router)

    info = await analyzer.get_vision_model_info()
    assert info["name"] == "gemma-vision"
    assert info["model_id"] == "google/gemma-3-12b-it"


@pytest.mark.asyncio
async def test_ui_element_detector_parsing_and_filtering():
    """Test structured parsing of raw element dictionaries into UIElement models with center points."""
    detector = UIElementDetector()

    raw = [
        {
            "id": "btn_save",
            "type": "button",
            "label": "Save Project",
            "bbox": {"x": 50, "y": 100, "width": 80, "height": 30},
            "confidence": 0.99,
        },
        {
            "id": "inp_name",
            "type": "input_field",
            "label": "Project Name",
            "bbox": {"x": 50, "y": 150, "width": 200, "height": 35},
            "confidence": 0.92,
        },
        {
            "id": "txt_note",
            "type": "text",
            "label": "All changes are autosaved",
            "bbox": {"x": 50, "y": 200, "width": 150, "height": 20},
            "confidence": 0.85,
        },
    ]

    elements = detector.parse_elements(raw, screen_width=1920, screen_height=1080)
    assert len(elements) == 3

    # Check center coordinate calculation
    btn = elements[0]
    assert btn.element_type == UIElementType.BUTTON
    assert btn.label == "Save Project"
    assert btn.bounding_box.center == (90, 115)  # 50 + 40, 100 + 15
    assert btn.is_clickable is True

    # Filtering
    buttons = detector.find_by_type(elements, UIElementType.BUTTON)
    assert len(buttons) == 1
    assert buttons[0].label == "Save Project"

    matched = detector.find_by_label(elements, "Save Project", exact=True)
    assert len(matched) == 1
    assert matched[0].element_id == "btn_save"

    matched_sub = detector.find_by_label(elements, "save")
    assert len(matched_sub) == 2  # matches "Save Project" and "...autosaved"


def test_visual_grounding_natural_language():
    """Test grounding of natural language intent into screen elements and coordinates."""
    grounding = VisualGroundingEngine()

    elements = [
        UIElement(
            element_id="btn_1",
            element_type=UIElementType.BUTTON,
            label="Settings",
            bounding_box=BoundingBox(x=100, y=200, width=100, height=40),
            confidence=0.95,
        ),
        UIElement(
            element_id="inp_1",
            element_type=UIElementType.INPUT_FIELD,
            label="Search Query",
            bounding_box=BoundingBox(x=300, y=200, width=200, height=40),
            confidence=0.90,
        ),
    ]

    # 1. Ground "click the Settings button"
    target1 = grounding.ground("click the Settings button", elements)
    assert target1.matched_element is not None
    assert target1.matched_element.element_id == "btn_1"
    assert target1.target_coordinates == (150, 220)
    assert target1.confidence > 0.8

    # 2. Ground "type in Search Query box"
    target2 = grounding.ground("type in Search Query box", elements)
    assert target2.matched_element is not None
    assert target2.matched_element.element_id == "inp_1"
    assert target2.target_coordinates == (400, 220)

    # 3. Ground unmatched query with fallback
    target3 = grounding.ground("nonexistent button", elements, fallback_coordinates=(500, 500))
    assert target3.target_coordinates == (500, 500)


@pytest.mark.asyncio
async def test_visual_control_coordinator_execution_and_permissions():
    """Test closed-loop click/type execution with PermissionGate checks."""
    # 1. Without permission gate -> should execute cleanly
    coordinator = VisualControlCoordinator()

    mock_elements = [
        {
            "id": "btn_deploy",
            "type": "button",
            "label": "Deploy",
            "bbox": {"x": 200, "y": 300, "width": 100, "height": 40},
            "confidence": 0.99,
        }
    ]

    result = await coordinator.execute_visual_click(
        query="click Deploy button",
        mock_pre_elements=mock_elements,
    )
    assert result.executed is True
    assert result.verification_status == VerificationStatus.SUCCESS
    assert result.coordinates == (250, 320)
    assert len(coordinator.history) == 1

    # 2. Type action
    type_res = await coordinator.execute_visual_type(
        query="Deploy",
        text="production",
        mock_pre_elements=mock_elements,
    )
    assert type_res.executed is True
    assert type_res.verification_status == VerificationStatus.SUCCESS

    # 3. Permission Gate blocking
    ws_mock = AsyncMock()
    gate = PermissionGate(ws_send=None)  # No interactive client -> blocks HIGH_IMPACT_ACTION
    gated_coordinator = VisualControlCoordinator(permission_gate=gate)

    denied_res = await gated_coordinator.execute_visual_click(
        query="click Deploy button",
        mock_pre_elements=mock_elements,
    )
    assert denied_res.executed is False
    assert "Permission denied" in (denied_res.error_message or "")


def test_visual_context_builder_bounded_summary():
    """Test formatting bounded visual context for agent prompt inclusion."""
    builder = VisualContextBuilder()

    elements = [
        UIElement(
            element_id="el_1",
            element_type=UIElementType.BUTTON,
            label="Submit",
            bounding_box=BoundingBox(x=10, y=20, width=50, height=25),
        )
    ]

    analysis = VisualAnalysisResult(
        analysis_id="vis_123",
        summary="Form modal displayed.",
        description="Form with submit button.",
        detected_elements=elements,
        active_window="User Registration",
    )

    ctx = builder.build_context(analysis, screenshot_path="/tmp/shot.png")
    prompt_str = ctx.format_for_prompt()

    assert "Active Window: User Registration" in prompt_str
    assert "Form modal displayed." in prompt_str
    assert "[BUTTON] 'Submit' at (10, 20, w:50, h:25) [clickable]" in prompt_str


@pytest.mark.asyncio
async def test_privacy_and_credential_protection():
    """Verify secrets and passwords on screen are sanitized from visual analysis."""
    analyzer = VisualUnderstandingEngine()

    # Secret in text
    sanitized = analyzer._sanitize_text("User entered password: supersecretpassword123 for auth")
    assert "supersecretpassword123" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    # API Token
    sanitized_tok = analyzer._sanitize_text("Found token: ghp_123456789012345678901234567890123456 in logs")
    assert "ghp_" not in sanitized_tok


@pytest.mark.asyncio
async def test_screen_capture_tool_parameters():
    """Verify ScreenCaptureTool integrates monitor, window, and region parameters."""
    tool = ScreenCaptureTool()
    assert tool.tool_id == "screen_capture"

    params = {
        "monitor_index": 0,
        "region": [10, 20, 300, 200],
        "output_path": "/tmp/custom_shot.png",
    }
    res = await tool.execute(params)
    assert res.success is True
    assert res.output["monitor_index"] == 0
    assert res.output["region"] == [10, 20, 300, 200]
    assert "custom_shot.png" in res.output["screenshot_path"]
