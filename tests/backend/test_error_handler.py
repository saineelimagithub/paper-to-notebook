"""
Error handler tests — verifies generic user-facing messages and no leak of internals.
Run: cd backend && python -m pytest ../tests/backend/test_error_handler.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from error_handler import safe_error_message


def test_generic_exception_returns_generic_message():
    exc = Exception("Traceback (most recent call last):\n  File '/app/main.py'...")
    msg = safe_error_message(exc)
    assert msg == "Generation failed. Please try again."


def test_file_path_never_in_message():
    exc = Exception("FileNotFoundError: /home/user/.env not found")
    msg = safe_error_message(exc)
    assert "/home" not in msg
    assert ".env" not in msg


def test_traceback_never_in_message():
    exc = Exception("Traceback (most recent call last):\n  File 'main.py', line 42")
    msg = safe_error_message(exc)
    assert "Traceback" not in msg
    assert "line 42" not in msg


def test_api_key_never_in_message():
    exc = Exception("Invalid API key: AIzaSyB1234567890")
    msg = safe_error_message(exc)
    assert "AIza" not in msg


def test_auth_error_recognized():
    """Errors with auth-related keywords should return API key message."""
    exc = Exception("401 Unauthorized: invalid API key")
    msg = safe_error_message(exc)
    assert msg == "Invalid API key."


def test_auth_error_permission_denied():
    exc = Exception("403 Forbidden: permission denied for this model")
    msg = safe_error_message(exc)
    assert msg == "Invalid API key."


def test_pdf_parse_error_recognized():
    exc = Exception("fitz.FileDataError: cannot open broken file")
    msg = safe_error_message(exc)
    assert msg == "PDF could not be parsed."


def test_pdf_error_pymupdf():
    exc = Exception("RuntimeError: cannot open document: format error")
    msg = safe_error_message(exc)
    assert msg == "PDF could not be parsed."


def test_value_error_generic():
    exc = ValueError("something went wrong internally")
    msg = safe_error_message(exc)
    assert msg == "Generation failed. Please try again."


def test_runtime_error_no_internals():
    exc = RuntimeError("pool connection failed at 10.0.0.1:5432")
    msg = safe_error_message(exc)
    assert "10.0.0.1" not in msg
    assert "5432" not in msg
