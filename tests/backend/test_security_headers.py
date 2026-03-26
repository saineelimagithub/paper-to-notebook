"""
Security headers tests — verifies all responses include required security headers
and CORS is tightened to explicit allowed headers.
Run: cd backend && python -m pytest ../tests/backend/test_security_headers.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def test_health_has_security_headers():
    """GET /health response must include all required security headers."""
    response = client.get("/health")
    assert response.status_code == 200
    for header, value in REQUIRED_HEADERS.items():
        assert header in response.headers, f"Missing header: {header}"
        assert response.headers[header] == value, (
            f"Header {header}: expected '{value}', got '{response.headers[header]}'"
        )


def test_health_has_csp_header():
    """GET /health must include Content-Security-Policy header."""
    response = client.get("/health")
    csp = response.headers.get("content-security-policy", "")
    assert "default-src" in csp


def test_cors_allows_explicit_headers_only():
    """CORS preflight must list explicit allowed headers, not wildcard."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Api-Key",
        },
    )
    assert response.status_code == 200
    allowed = response.headers.get("access-control-allow-headers", "")
    # Must not be wildcard
    assert allowed != "*", "allow_headers should not be wildcard '*'"
    # Must include the headers we need
    allowed_lower = allowed.lower()
    assert "content-type" in allowed_lower
    assert "x-api-key" in allowed_lower


def test_cors_rejects_disallowed_origin():
    """CORS must reject requests from unknown origins."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Either no allow-origin header or it doesn't match the evil origin
    allow_origin = response.headers.get("access-control-allow-origin", "")
    assert "evil.example.com" not in allow_origin


def test_404_has_security_headers():
    """Even 404 responses must include security headers."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code in (404, 405)
    for header in REQUIRED_HEADERS:
        assert header in response.headers, f"Missing header on error response: {header}"
