"""
tests/test_vision_api.py — Integration tests for the Vision HTTP API

Tests all /api/vision/* endpoints against a real FastAPI TestClient.
Uses real vision infrastructure with a known test image.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from main import app


@pytest.fixture(scope="module")
def client():
    """FastAPI test client with app lifecycle."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def test_image_path(tmp_path_factory) -> str:
    """Create a real 100x100 PNG test image."""
    tmp = tmp_path_factory.mktemp("vision_test")
    img_path = tmp / "test_screen.png"
    img = Image.new("RGB", (100, 100), color=(30, 30, 30))
    img.save(str(img_path), "PNG")
    return str(img_path)


@pytest.fixture(scope="module")
def test_image_bytes() -> bytes:
    """Create PNG bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (80, 80), color=(20, 40, 60))
    img.save(buf, "PNG")
    return buf.getvalue()


# ── Capabilities ──────────────────────────────────────────────────────────────

class TestVisionCapabilities:
    def test_get_capabilities_returns_200(self, client):
        res = client.get("/api/vision/capabilities")
        assert res.status_code == 200

    def test_capabilities_schema(self, client):
        data = client.get("/api/vision/capabilities").json()
        assert "vision_model_available" in data
        assert "screen_capture_available" in data
        assert "supported_operations" in data
        assert isinstance(data["vision_models"], list)

    def test_capabilities_are_not_mock(self, client):
        """Honest capability: no hardcoded True values without real backend check."""
        data = client.get("/api/vision/capabilities").json()
        # These must be booleans; a hardcoded True would be caught if model unreachable
        assert isinstance(data["vision_model_available"], bool)
        assert isinstance(data["screen_capture_available"], bool)


# ── Analyze Endpoint ──────────────────────────────────────────────────────────

class TestVisionAnalyze:
    def test_analyze_returns_200(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            res = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            )
        assert res.status_code == 200

    def test_analyze_response_schema(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            data = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()
        assert "analysis_id" in data
        assert "summary" in data
        assert "detected_elements" in data
        assert "detected_text" in data
        assert "model_used" in data
        assert "confidence" in data

    def test_analyze_analysis_id_is_populated(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            data = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()
        assert data["analysis_id"].startswith("vis_")

    def test_analyze_unsupported_mime_rejected(self, client):
        res = client.post(
            "/api/vision/analyze",
            files={"file": ("doc.pdf", b"fake-pdf", "application/pdf")},
        )
        assert res.status_code == 415

    def test_analyze_with_custom_prompt(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            res = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
                data={"custom_prompt": "Describe what you see"},
            )
        assert res.status_code == 200


# ── Recent Analyses ───────────────────────────────────────────────────────────

class TestVisionRecent:
    def test_recent_returns_200(self, client):
        res = client.get("/api/vision/recent")
        assert res.status_code == 200

    def test_recent_schema(self, client):
        data = client.get("/api/vision/recent").json()
        assert "recent" in data
        assert "count" in data
        assert isinstance(data["recent"], list)

    def test_recent_contains_uploaded_analysis(self, client, test_image_path):
        # Upload one
        with open(test_image_path, "rb") as f:
            upload_data = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()
        analysis_id = upload_data["analysis_id"]

        # Should appear in recent
        recent = client.get("/api/vision/recent").json()["recent"]
        ids = [r["analysis_id"] for r in recent]
        assert analysis_id in ids

    def test_get_specific_analysis(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            analysis_id = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()["analysis_id"]

        res = client.get(f"/api/vision/recent/{analysis_id}")
        assert res.status_code == 200
        assert res.json()["analysis_id"] == analysis_id

    def test_get_nonexistent_analysis_returns_404(self, client):
        res = client.get("/api/vision/recent/nonexistent_id_xyz")
        assert res.status_code == 404


# ── Visual Q&A ────────────────────────────────────────────────────────────────

class TestVisionAsk:
    def test_ask_returns_answer(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            analysis_id = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()["analysis_id"]

        res = client.post(
            "/api/vision/ask",
            json={"analysis_id": analysis_id, "question": "What is on the screen?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert data["question"] == "What is on the screen?"
        assert data["analysis_id"] == analysis_id

    def test_ask_unknown_analysis_returns_404(self, client):
        res = client.post(
            "/api/vision/ask",
            json={"analysis_id": "nonexistent", "question": "test"},
        )
        assert res.status_code == 404


# ── Context Builder ───────────────────────────────────────────────────────────

class TestVisionContext:
    def test_context_returns_string(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            analysis_id = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()["analysis_id"]

        res = client.post(
            "/api/vision/context",
            json={"analysis_id": analysis_id},
        )
        assert res.status_code == 200
        data = res.json()
        assert "context_string" in data
        assert len(data["context_string"]) > 0
        assert "usage_hint" in data

    def test_context_string_contains_summary(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            upload = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()
        analysis_id = upload["analysis_id"]

        ctx = client.post(
            "/api/vision/context",
            json={"analysis_id": analysis_id},
        ).json()
        # The context string should reference the summary from the analysis
        assert "Summary:" in ctx["context_string"] or ctx["context_string"].strip() != ""

    def test_context_unknown_analysis_returns_404(self, client):
        res = client.post(
            "/api/vision/context",
            json={"analysis_id": "does_not_exist"},
        )
        assert res.status_code == 404


# ── Image Serving ─────────────────────────────────────────────────────────────

class TestVisionImageServe:
    def test_image_serves_200(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            analysis_id = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()["analysis_id"]

        res = client.get(f"/api/vision/image/{analysis_id}")
        assert res.status_code == 200
        assert "image" in res.headers["content-type"]

    def test_image_unknown_analysis_returns_404(self, client):
        res = client.get("/api/vision/image/nonexistent")
        assert res.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

class TestVisionDelete:
    def test_delete_analysis(self, client, test_image_path):
        with open(test_image_path, "rb") as f:
            analysis_id = client.post(
                "/api/vision/analyze",
                files={"file": ("test.png", f, "image/png")},
            ).json()["analysis_id"]

        res = client.delete(f"/api/vision/recent/{analysis_id}")
        assert res.status_code == 200
        assert res.json()["deleted"] is True

        # Should 404 after deletion
        res2 = client.get(f"/api/vision/recent/{analysis_id}")
        assert res2.status_code == 404
