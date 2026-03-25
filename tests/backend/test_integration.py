"""
Integration tests for FastAPI endpoints — full wiring with all modules implemented.
Run: cd backend && python -m pytest ../tests/backend/test_integration.py -v
"""
import sys
import os
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────


def test_health_returns_200_ok():
    """GET /health must return 200 with {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_missing_fields_returns_422():
    """POST /generate without required fields must return 422."""
    response = client.post("/generate")
    assert response.status_code == 422


def test_generate_missing_api_key_returns_422():
    """POST /generate without api_key must return 422."""
    import fitz

    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/generate",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422


def test_generate_non_pdf_returns_400():
    """POST /generate with a non-PDF file must return 400."""
    response = client.post(
        "/generate",
        data={"api_key": "sk-test123"},
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_generate_non_pdf_extension_returns_400():
    """POST /generate with a .txt extension must return 400."""
    response = client.post(
        "/generate",
        data={"api_key": "sk-test"},
        files={"file": ("report.txt", b"some content", "application/pdf")},
    )
    assert response.status_code == 400


def test_generate_valid_pdf_returns_job_id():
    """POST /generate with a valid PDF must return a job_id immediately."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Test Paper Title", fontsize=18)
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/generate",
        data={"api_key": "sk-test-key"},
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# GET /stream/{job_id}
# ─────────────────────────────────────────────────────────────────────────────


def test_stream_invalid_job_id_returns_404():
    """GET /stream/{job_id} with unknown job_id must return 404."""
    response = client.get("/stream/nonexistent-job-id-99999")
    assert response.status_code == 404


def test_stream_invalid_uuid_returns_404():
    """GET /stream with a completely invalid ID must return 404."""
    response = client.get("/stream/this-is-not-a-real-job")
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# POST /publish
# ─────────────────────────────────────────────────────────────────────────────


def test_publish_missing_fields_returns_422():
    """POST /publish without required fields must return 422."""
    response = client.post("/publish")
    assert response.status_code == 422


def test_publish_missing_title_returns_422():
    """POST /publish without title must return 422."""
    import base64
    notebook_b64 = base64.b64encode(b'{"cells": []}').decode()
    response = client.post("/publish", data={"notebook_b64": notebook_b64})
    assert response.status_code == 422


def test_publish_missing_notebook_b64_returns_422():
    """POST /publish without notebook_b64 must return 422."""
    response = client.post("/publish", data={"title": "My Notebook"})
    assert response.status_code == 422


def test_publish_without_github_token_returns_503(monkeypatch):
    """POST /publish without GITHUB_TOKEN env var must return 503."""
    import base64
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    notebook_b64 = base64.b64encode(b'{"cells": []}').decode()
    response = client.post(
        "/publish",
        data={"notebook_b64": notebook_b64, "title": "Test Notebook"},
    )
    assert response.status_code == 503
