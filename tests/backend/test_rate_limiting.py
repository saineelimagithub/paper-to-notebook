"""
Rate limiting tests — verifies /generate and /publish are rate-limited.
Run: cd backend && python -m pytest ../tests/backend/test_rate_limiting.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import fitz
import pytest
from fastapi.testclient import TestClient
from main import app, limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset rate limiter state before each test."""
    limiter.reset()
    yield


def _make_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Rate Limit Test", fontsize=18)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_generate_within_limit_succeeds():
    """A single POST /generate should succeed (not rate-limited)."""
    pdf_bytes = _make_pdf()
    response = client.post(
        "/generate",
        headers={"X-Api-Key": "sk-test-key"},
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200


def test_generate_rate_limit_triggers_429():
    """POST /generate should return 429 after exceeding 5 requests/minute."""
    pdf_bytes = _make_pdf()
    statuses = []
    for _ in range(7):
        response = client.post(
            "/generate",
            headers={"X-Api-Key": "sk-test-key"},
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
        )
        statuses.append(response.status_code)

    assert 429 in statuses, f"Expected at least one 429, got: {statuses}"
    # First 5 should be 200, rest 429
    assert statuses[:5] == [200] * 5
    assert all(s == 429 for s in statuses[5:])


def test_publish_rate_limit_triggers_429():
    """POST /publish should return 429 after exceeding 10 requests/minute."""
    import base64
    notebook_b64 = base64.b64encode(b'{"cells": []}').decode()

    statuses = []
    for _ in range(12):
        response = client.post(
            "/publish",
            data={"notebook_b64": notebook_b64, "title": "Test"},
        )
        statuses.append(response.status_code)

    # Some should be 429 (after 10), some might be 503 (no GITHUB_TOKEN)
    assert 429 in statuses, f"Expected at least one 429, got: {statuses}"
