"""
Smoke tests for FastAPI backend scaffold.
Run: cd backend && python -m pytest ../tests/backend/test_app_smoke.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_ok():
    """Health endpoint must return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_frontend_origin():
    """CORS must allow requests from the Vite dev server origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    # FastAPI CORS middleware returns 200 for preflight
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_generate_endpoint_exists():
    """POST /generate must exist (returns 422 without body, not 404)."""
    response = client.post("/generate")
    assert response.status_code == 422  # Unprocessable Entity — endpoint exists but fields missing


def test_publish_endpoint_exists():
    """POST /publish must exist (returns 422 without body, not 404)."""
    response = client.post("/publish")
    assert response.status_code == 422
