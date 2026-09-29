"""
api.vision — Vision REST endpoints for Kora

Provides real image analysis, server-side screen capture, visual Q&A,
OCR text extraction, and context injection into the agent session.

All endpoints use the existing vision module infrastructure:
  vision.capture  → ScreenCaptureEngine  (platform adapter)
  vision.analyzer → VisualUnderstandingEngine  (model router → gemma-vision)
  vision.context  → VisualContextBuilder  (prompt-ready context for agent)

No mock data is introduced here.  If the vision model is unavailable the
endpoints return an honest error rather than synthetic results.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.deps import get_model_registry
from models.registry import ModelRegistry
from vision.analyzer import VisualUnderstandingEngine
from vision.capture import ScreenCaptureEngine
from vision.context import VisualContextBuilder
from vision.types import CaptureOptions, CaptureTarget

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])

# ── Ephemeral storage for session results ────────────────────────────────────
# Maps analysis_id → VisualAnalysisResult.to_dict()
_recent_analyses: dict[str, dict[str, Any]] = {}
_MAX_RECENT = 20

# Upload scratch directory
_VISION_UPLOAD_DIR = Path(tempfile.gettempdir()) / "kora_vision_uploads"
_VISION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_registry() -> ModelRegistry:
    return get_model_registry()


def _build_analyzer() -> VisualUnderstandingEngine:
    registry = _get_registry()
    return VisualUnderstandingEngine(registry=registry)


def _store_result(result_dict: dict[str, Any]) -> None:
    aid = result_dict.get("analysis_id", str(uuid.uuid4()))
    _recent_analyses[aid] = result_dict
    # Trim to most recent N
    if len(_recent_analyses) > _MAX_RECENT:
        oldest = next(iter(_recent_analyses))
        del _recent_analyses[oldest]


# ── Schemas ──────────────────────────────────────────────────────────────────

class VisionQuestionRequest(BaseModel):
    analysis_id: str
    question: str


class VisionContextRequest(BaseModel):
    analysis_id: str
    include_elements: bool = True
    include_ocr: bool = True


class VisionCaptureRequest(BaseModel):
    target: str = "full_screen"   # full_screen | window | region
    monitor_index: int | None = None
    window_id: str | None = None
    region: list[int] | None = None  # [x, y, w, h]
    analyze: bool = True
    custom_prompt: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    custom_prompt: str | None = Form(default=None),
) -> dict[str, Any]:
    """
    Upload an image and run full visual analysis via the vision model.

    Accepts: PNG, JPEG, WEBP, BMP.
    Returns: VisualAnalysisResult — detected elements, OCR text, summary, model used.

    The analysis_id in the response can be used with /ask and /context endpoints.
    """
    # Validate MIME type
    allowed_mime = {"image/png", "image/jpeg", "image/webp", "image/bmp", "image/gif"}
    content_type = file.content_type or ""
    if content_type.split(";")[0].strip() not in allowed_mime:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Accepted: PNG, JPEG, WEBP, BMP, GIF",
        )

    # Limit to 20 MB
    max_bytes = 20 * 1024 * 1024
    save_path = _VISION_UPLOAD_DIR / f"upload_{uuid.uuid4().hex}.png"

    try:
        with save_path.open("wb") as dest:
            total = 0
            while chunk := await file.read(65536):
                total += len(chunk)
                if total > max_bytes:
                    save_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Image too large (max 20 MB)")
                dest.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded image: {exc}")

    analyzer = _build_analyzer()
    try:
        result = await analyzer.analyze_screen(
            image_path=str(save_path),
            custom_prompt=custom_prompt,
        )
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        logger.exception("vision_analyze_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {exc}")

    result_dict = result.to_dict()
    result_dict["image_path"] = str(save_path)
    _store_result(result_dict)

    logger.info(
        "vision_analyze_complete",
        analysis_id=result.analysis_id,
        elements=len(result.detected_elements),
        model=result.model_used,
    )
    return result_dict


@router.post("/capture")
async def capture_and_analyze(req: VisionCaptureRequest) -> dict[str, Any]:
    """
    Trigger a server-side screen capture via the ScreenCaptureEngine, then
    optionally run full visual analysis.

    Returns: capture metadata + (if analyze=True) VisualAnalysisResult.
    """
    # Map request target string to CaptureTarget enum
    target_map = {
        "full_screen": CaptureTarget.FULL_SCREEN,
        "monitor": CaptureTarget.MONITOR,
        "window": CaptureTarget.WINDOW,
        "region": CaptureTarget.REGION,
    }
    target = target_map.get(req.target, CaptureTarget.FULL_SCREEN)

    region: tuple[int, int, int, int] | None = None
    if req.region and len(req.region) == 4:
        region = (req.region[0], req.region[1], req.region[2], req.region[3])

    capture_opts = CaptureOptions(
        target=target,
        monitor_index=req.monitor_index,
        window_id=req.window_id,
        region=region,
        ephemeral=False,  # Keep for subsequent analysis and serving
    )

    capture_engine = ScreenCaptureEngine()
    try:
        capture_result = await capture_engine.capture(capture_opts)
    except Exception as exc:
        logger.exception("vision_capture_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Screen capture failed: {exc}")

    response: dict[str, Any] = capture_result.to_dict()

    if req.analyze:
        analyzer = _build_analyzer()
        try:
            analysis = await analyzer.analyze_screen(
                image_path=capture_result.image_path,
                custom_prompt=req.custom_prompt,
            )
            analysis_dict = analysis.to_dict()
            analysis_dict["image_path"] = capture_result.image_path
            _store_result(analysis_dict)
            response["analysis"] = analysis_dict
        except Exception as exc:
            logger.exception("vision_capture_analyze_failed", error=str(exc))
            response["analysis_error"] = str(exc)

    return response


@router.post("/ask")
async def ask_visual_question(req: VisionQuestionRequest) -> dict[str, Any]:
    """
    Ask a natural-language question about a previously analyzed image.

    The analysis_id must correspond to a result from /analyze or /capture.
    Returns: the question, the model's answer, and which model answered.
    """
    if req.analysis_id not in _recent_analyses:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{req.analysis_id}' not found. Run /analyze or /capture first.",
        )

    stored = _recent_analyses[req.analysis_id]
    image_path = stored.get("image_path", "")

    analyzer = _build_analyzer()
    try:
        answer = await analyzer.ask_visual_question(
            image_path=image_path,
            question=req.question,
        )
    except Exception as exc:
        logger.exception("vision_vqa_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Visual Q&A failed: {exc}")

    model_info = await analyzer.get_vision_model_info()
    return {
        "analysis_id": req.analysis_id,
        "question": req.question,
        "answer": answer,
        "model_used": model_info.get("name", "unknown"),
    }


@router.post("/context")
async def build_vision_context(req: VisionContextRequest) -> dict[str, Any]:
    """
    Build a prompt-ready visual context string from a prior analysis.

    This output is designed to be injected directly into a Kora CHAT_REQUEST
    as additional context, bridging vision results into the agent's reasoning.

    Frontend should send this as a prefix in the chat message:
      {type: "CHAT_REQUEST", payload: {message: <context_string> + user_question}}
    """
    if req.analysis_id not in _recent_analyses:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{req.analysis_id}' not found.",
        )

    stored = _recent_analyses[req.analysis_id]

    # Reconstruct a lightweight VisualAnalysisResult-compatible dict for the builder
    from vision.types import BoundingBox, UIElement, UIElementType, VisualAnalysisResult

    elements = []
    if req.include_elements:
        for el_dict in stored.get("detected_elements", []):
            bbox_dict = el_dict.get("bounding_box", {})
            bbox = BoundingBox(
                x=bbox_dict.get("x", 0),
                y=bbox_dict.get("y", 0),
                width=bbox_dict.get("width", 0),
                height=bbox_dict.get("height", 0),
            )
            try:
                el_type = UIElementType(el_dict.get("element_type", "custom"))
            except ValueError:
                el_type = UIElementType.CUSTOM
            elements.append(UIElement(
                element_id=el_dict.get("element_id", str(uuid.uuid4())),
                element_type=el_type,
                label=el_dict.get("label", ""),
                bounding_box=bbox,
                confidence=el_dict.get("confidence", 1.0),
                is_clickable=el_dict.get("is_clickable", True),
            ))

    ocr_texts = stored.get("detected_text", []) if req.include_ocr else []

    analysis = VisualAnalysisResult(
        analysis_id=req.analysis_id,
        summary=stored.get("summary", ""),
        description=stored.get("description", ""),
        detected_elements=elements,
        detected_text=ocr_texts,
        active_window=stored.get("active_window"),
        confidence=stored.get("confidence", 1.0),
        model_used=stored.get("model_used", ""),
    )

    builder = VisualContextBuilder()
    screen_ctx = builder.build_context(
        analysis=analysis,
        screenshot_path=stored.get("image_path", ""),
    )

    context_string = screen_ctx.format_for_prompt()

    return {
        "analysis_id": req.analysis_id,
        "context_string": context_string,
        "summary": screen_ctx.summary,
        "elements_summary": screen_ctx.elements_summary,
        "active_window": screen_ctx.active_window_info,
        "confidence": screen_ctx.confidence,
        "usage_hint": (
            "Send context_string as a prefix in a WS CHAT_REQUEST message payload. "
            "Example: {type: 'CHAT_REQUEST', payload: {message: context_string + '\\n\\n' + user_question}}"
        ),
    }


@router.get("/recent")
async def list_recent_analyses() -> dict[str, Any]:
    """
    Return the most recent vision analysis results (up to 20).
    Ordered newest-first.
    """
    items = list(reversed(list(_recent_analyses.values())))
    # Strip full raw_response to keep payload size reasonable
    slim = [
        {
            "analysis_id": r.get("analysis_id"),
            "summary": r.get("summary"),
            "model_used": r.get("model_used"),
            "element_count": len(r.get("detected_elements", [])),
            "ocr_text_count": len(r.get("detected_text", [])),
            "timestamp": r.get("timestamp"),
            "confidence": r.get("confidence"),
        }
        for r in items
    ]
    return {"recent": slim, "count": len(slim)}


@router.get("/recent/{analysis_id}")
async def get_analysis(analysis_id: str) -> dict[str, Any]:
    """Return the full result for a specific analysis_id."""
    if analysis_id not in _recent_analyses:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    return _recent_analyses[analysis_id]


@router.get("/image/{analysis_id}")
async def serve_analysis_image(analysis_id: str) -> FileResponse:
    """
    Serve the captured/uploaded image for an analysis result.
    Used by the Flutter frontend to display the image preview.
    """
    if analysis_id not in _recent_analyses:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    img_path = _recent_analyses[analysis_id].get("image_path", "")
    if not img_path or not os.path.isfile(img_path):
        raise HTTPException(status_code=404, detail="Image file not available")
    return FileResponse(img_path, media_type="image/png")


@router.delete("/recent/{analysis_id}")
async def delete_analysis(analysis_id: str) -> dict[str, Any]:
    """Delete a stored analysis result and its image file."""
    if analysis_id not in _recent_analyses:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    stored = _recent_analyses.pop(analysis_id)
    img_path = stored.get("image_path", "")
    if img_path and os.path.isfile(img_path):
        try:
            os.unlink(img_path)
        except OSError:
            pass
    return {"deleted": True, "analysis_id": analysis_id}


@router.get("/capabilities")
async def get_vision_capabilities() -> dict[str, Any]:
    """
    Return honest information about what the vision backend can actually do.
    The frontend uses this to show/hide features based on real availability.
    """
    registry = _get_registry()
    vision_models = [
        {"name": cfg.name, "model_id": cfg.model_id, "provider": cfg.provider}
        for cfg in registry.all()
        if "vision" in cfg.capabilities
    ]
    has_vision_model = len(vision_models) > 0

    # Check screen capture capability via platform adapter
    can_capture = False
    capture_error: str | None = None
    try:
        from vision.capture import ScreenCaptureEngine
        # Just instantiating the capture engine verifies the platform adapter loads
        _test_engine = ScreenCaptureEngine()
        can_capture = True
    except Exception as exc:
        capture_error = str(exc)

    return {
        "vision_model_available": has_vision_model,
        "vision_models": vision_models,
        "screen_capture_available": can_capture,
        "screen_capture_error": capture_error,
        "supported_operations": [
            "image_upload_and_analyze",
            "screen_capture_and_analyze",
            "visual_question_answering",
            "ui_element_detection",
            "ocr_text_extraction",
            "agent_context_injection",
        ] if has_vision_model else [],
        "note": (
            "Vision analysis requires the gemma-vision model to be reachable via the HuggingFace provider. "
            "Screen capture requires a desktop display environment."
        ),
    }
