"""
Tests for gist_publisher.publish_to_gist()
Run: cd backend && python -m pytest ../tests/backend/test_gist_publisher.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from unittest.mock import MagicMock, patch

import pytest

from gist_publisher import publish_to_gist


SAMPLE_NOTEBOOK_JSON = '{"nbformat": 4, "cells": []}'
SAMPLE_TITLE = "Attention Is All You Need"


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_returns_none_when_no_token(monkeypatch):
    """publish_to_gist() must return None when GITHUB_TOKEN is not set."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = publish_to_gist(SAMPLE_NOTEBOOK_JSON, SAMPLE_TITLE)
    assert result is None


def test_calls_correct_github_api_url(monkeypatch):
    """publish_to_gist() must POST to https://api.github.com/gists."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "abc123def456",
        "owner": {"login": "testuser"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("gist_publisher.httpx.post", return_value=mock_response) as mock_post:
        publish_to_gist(SAMPLE_NOTEBOOK_JSON, SAMPLE_TITLE)
        call_args = mock_post.call_args
        assert call_args.args[0] == "https://api.github.com/gists"


def test_sends_correct_headers(monkeypatch):
    """publish_to_gist() must send Authorization and GitHub API version headers."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "abc123",
        "owner": {"login": "testuser"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("gist_publisher.httpx.post", return_value=mock_response) as mock_post:
        publish_to_gist(SAMPLE_NOTEBOOK_JSON, SAMPLE_TITLE)
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer ghp_testtoken123"
        assert "application/vnd.github" in headers["Accept"]
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_sends_correct_payload_structure(monkeypatch):
    """publish_to_gist() must send payload with description, public, and files."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "abc123",
        "owner": {"login": "testuser"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("gist_publisher.httpx.post", return_value=mock_response) as mock_post:
        publish_to_gist(SAMPLE_NOTEBOOK_JSON, SAMPLE_TITLE)
        payload = mock_post.call_args.kwargs["json"]
        assert "description" in payload
        assert payload["public"] is True
        assert "files" in payload
        # The files dict should have exactly one key (the notebook filename)
        assert len(payload["files"]) == 1
        # The file content must be the notebook JSON
        filename = list(payload["files"].keys())[0]
        assert payload["files"][filename]["content"] == SAMPLE_NOTEBOOK_JSON


def test_returns_correct_colab_url(monkeypatch):
    """publish_to_gist() must return a valid Colab URL on success."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "abc123def456",
        "owner": {"login": "octocat"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("gist_publisher.httpx.post", return_value=mock_response):
        result = publish_to_gist(SAMPLE_NOTEBOOK_JSON, SAMPLE_TITLE)

    expected = "https://colab.research.google.com/gist/octocat/abc123def456"
    assert result == expected


def test_filename_sanitization_special_chars(monkeypatch):
    """publish_to_gist() must sanitize special characters in the title for the filename."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "x", "owner": {"login": "u"}}
    mock_response.raise_for_status = MagicMock()

    with patch("gist_publisher.httpx.post", return_value=mock_response) as mock_post:
        publish_to_gist(SAMPLE_NOTEBOOK_JSON, "Title: With! Special@Chars?")
        payload = mock_post.call_args.kwargs["json"]
        filename = list(payload["files"].keys())[0]
        # Filename should end with .ipynb and not contain problematic chars
        assert filename.endswith(".ipynb")
        # Should not contain colons or exclamation marks
        assert ":" not in filename
        assert "!" not in filename
        assert "@" not in filename
        assert "?" not in filename


def test_filename_truncation_long_title(monkeypatch):
    """publish_to_gist() must truncate very long titles to max 80 chars (before .ipynb)."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "x", "owner": {"login": "u"}}
    mock_response.raise_for_status = MagicMock()

    long_title = "A" * 200

    with patch("gist_publisher.httpx.post", return_value=mock_response) as mock_post:
        publish_to_gist(SAMPLE_NOTEBOOK_JSON, long_title)
        payload = mock_post.call_args.kwargs["json"]
        filename = list(payload["files"].keys())[0]
        # Stem (without .ipynb) should be at most 80 chars
        stem = filename[: -len(".ipynb")]
        assert len(stem) <= 80
