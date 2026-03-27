"""
Integration tests for the full /generate → /stream flow with mocked Gemini.
Tests the complete pipeline: upload PDF → background generation → SSE stream → done event.
Run: cd backend && python -m pytest ../tests/backend/test_api_integration.py -v
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from unittest.mock import MagicMock, patch

import fitz
import pytest
from fastapi.testclient import TestClient
from main import app
from job_store import _jobs

# Reset rate limiter between tests
from main import limiter


@pytest.fixture(autouse=True)
def reset_state():
    """Clear jobs and reset rate limiter before each test."""
    _jobs.clear()
    limiter.reset()
    yield
    _jobs.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_pdf(text: str = "Test Paper Title") -> bytes:
    """Create a minimal PDF with text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=18)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


SAMPLE_GEMINI_JSON = {
    "summary_bullets": [
        "Implements the core algorithm",
        "Synthetic dataset with 1000 samples",
        "Ablation over 3 hyperparameters",
    ],
    "cells": [
        {"type": "markdown", "source": "# Test Notebook\nGenerated from paper."},
        {"type": "code", "source": "import numpy as np\nprint('setup')"},
        {"type": "markdown", "source": "## Background\nTheory here."},
        {"type": "code", "source": "def algorithm(x):\n    return x * 2"},
        {"type": "code", "source": "data = np.random.randn(100, 5)"},
        {"type": "code", "source": "results = algorithm(data)"},
        {"type": "markdown", "source": "## Summary\nDone."},
    ],
}


def _mock_gemini():
    """Create a mock Gemini response."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(SAMPLE_GEMINI_JSON)
    return mock_response


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Full generate → stream → done flow with mocked Gemini
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_and_stream_full_flow():
    """POST /generate + GET /stream should produce SSE events ending in done."""
    with patch("notebook_generator.genai") as mock_genai, \
         patch("gist_publisher.httpx.post") as mock_gist_post:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini()
        mock_genai.Client.return_value = mock_client

        mock_gist_resp = MagicMock()
        mock_gist_resp.json.return_value = {"id": "gist123", "owner": {"login": "testuser"}}
        mock_gist_resp.raise_for_status = MagicMock()
        mock_gist_post.return_value = mock_gist_resp

        client = TestClient(app)

        # Step 1: POST /generate
        pdf_bytes = _make_pdf("Attention Is All You Need")
        response = client.post(
            "/generate",
            headers={"X-Api-Key": "AIzaTestKey123"},
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        assert len(job_id) == 36  # UUID format

        # Step 2: GET /stream/{job_id} — collect SSE events
        time.sleep(0.5)

        stream_resp = client.get(f"/stream/{job_id}")
        assert stream_resp.status_code == 200

        # Parse SSE events
        events = []
        for line in stream_resp.text.strip().split("\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Should have at least one progress event and one done event
        assert len(events) >= 2
        types = [e["type"] for e in events]
        assert "progress" in types
        assert "done" in types

        # The done event should have notebook_b64
        done_event = [e for e in events if e["type"] == "done"][0]
        assert "notebook_b64" in done_event
        assert len(done_event["notebook_b64"]) > 0
        assert "findings" in done_event


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Valid PDF returns job_id immediately
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_valid_pdf_returns_job_id():
    """POST /generate with valid PDF + X-Api-Key should return 200 + job_id."""
    client = TestClient(app)
    pdf_bytes = _make_pdf()
    response = client.post(
        "/generate",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) == 36


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Invalid PDF returns 400
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_invalid_pdf_returns_400():
    """POST /generate with non-PDF file should return 400."""
    client = TestClient(app)
    response = client.post(
        "/generate",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Rate limit triggers 429
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_rate_limit_returns_429():
    """POST /generate should return 429 after exceeding 5/minute limit."""
    client = TestClient(app)
    pdf_bytes = _make_pdf()

    for i in range(5):
        resp = client.post(
            "/generate",
            headers={"X-Api-Key": "test-key"},
            files={"file": (f"paper{i}.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200

    # 6th request should be rate limited
    resp = client.post(
        "/generate",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("paper5.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 429


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Invalid UUID returns 400
# ─────────────────────────────────────────────────────────────────────────────


def test_stream_invalid_uuid_returns_400():
    """GET /stream with non-UUID string should return 400."""
    client = TestClient(app)
    response = client.get("/stream/not-a-valid-uuid")
    assert response.status_code == 400
    assert "Invalid job ID" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Unknown UUID returns 404
# ─────────────────────────────────────────────────────────────────────────────


def test_stream_unknown_uuid_returns_404():
    """GET /stream with valid UUID but unknown job should return 404."""
    client = TestClient(app)
    response = client.get("/stream/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Missing X-Api-Key returns 422
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_missing_api_key_returns_422():
    """POST /generate without X-Api-Key header should return 422."""
    client = TestClient(app)
    pdf_bytes = _make_pdf()
    response = client.post(
        "/generate",
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: SSE done event contains expected fields
# ─────────────────────────────────────────────────────────────────────────────


def test_sse_done_event_structure():
    """The SSE done event should contain type, message, elapsed, notebook_b64, colab_url, findings."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini()
        mock_genai.Client.return_value = mock_client

        with patch("gist_publisher.httpx.post") as mock_gist_post:
            mock_gist_resp = MagicMock()
            mock_gist_resp.json.return_value = {"id": "g123", "owner": {"login": "u"}}
            mock_gist_resp.raise_for_status = MagicMock()
            mock_gist_post.return_value = mock_gist_resp

            client = TestClient(app)
            pdf_bytes = _make_pdf()
            resp = client.post(
                "/generate",
                headers={"X-Api-Key": "test-key"},
                files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
            )
            job_id = resp.json()["job_id"]

            time.sleep(0.5)
            stream_resp = client.get(f"/stream/{job_id}")
            events = []
            for line in stream_resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            done_events = [e for e in events if e["type"] == "done"]
            assert len(done_events) == 1

            done = done_events[0]
            assert "type" in done
            assert "message" in done
            assert "elapsed" in done
            assert "notebook_b64" in done
            assert "colab_url" in done
            assert "findings" in done
            assert isinstance(done["findings"], list)
