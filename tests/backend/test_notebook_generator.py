"""
Tests for notebook_generator.build_notebook() and generate_notebook()
Run: cd backend && python -m pytest ../tests/backend/test_notebook_generator.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import json
from unittest.mock import MagicMock, patch

import nbformat
import pytest

from notebook_generator import build_notebook, generate_notebook


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_CELLS = [
    {"type": "markdown", "source": "# Title\nThis is the title cell."},
    {"type": "code", "source": "import numpy as np\nprint('hello')"},
    {"type": "markdown", "source": "## Background\nSome theory here."},
    {"type": "code", "source": "x = np.array([1, 2, 3])"},
    {"type": "markdown", "source": "## Algorithm\nPseudocode here."},
    {"type": "code", "source": "def my_algo(x):\n    return x * 2"},
    {"type": "code", "source": "data = np.random.randn(1000, 10)"},
    {"type": "code", "source": "results = my_algo(data)"},
    {"type": "code", "source": "import matplotlib.pyplot as plt\nplt.plot([1,2,3])"},
    {"type": "markdown", "source": "## Summary\nConclusion here."},
]

SAMPLE_GEMINI_RESPONSE = {
    "summary_bullets": [
        "Implements the core attention mechanism",
        "Includes synthetic dataset generation",
        "Ablation study over 3 hyperparameters",
    ],
    "cells": SAMPLE_CELLS,
}


# ─────────────────────────────────────────────────────────────────────────────
# build_notebook() tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_notebook_returns_notebook_node():
    """build_notebook() must return a NotebookNode."""
    nb = build_notebook(SAMPLE_CELLS)
    assert isinstance(nb, nbformat.NotebookNode)


def test_build_notebook_passes_validation():
    """Returned notebook must pass nbformat.validate()."""
    nb = build_notebook(SAMPLE_CELLS)
    nbformat.validate(nb)  # raises if invalid


def test_build_notebook_has_correct_metadata():
    """Notebook must have kernelspec and language_info metadata."""
    nb = build_notebook(SAMPLE_CELLS)
    assert "kernelspec" in nb.metadata
    assert nb.metadata["kernelspec"]["language"] == "python"
    assert "language_info" in nb.metadata
    assert nb.metadata["language_info"]["name"] == "python"


def test_build_notebook_has_colab_metadata():
    """Notebook must have colab metadata for Google Colab compatibility."""
    nb = build_notebook(SAMPLE_CELLS)
    assert "colab" in nb.metadata


def test_build_notebook_cell_count():
    """Notebook must contain same number of cells as input."""
    nb = build_notebook(SAMPLE_CELLS)
    assert len(nb.cells) == len(SAMPLE_CELLS)


def test_build_notebook_markdown_cells():
    """Markdown cells must be created with correct source."""
    nb = build_notebook(SAMPLE_CELLS)
    markdown_cells = [c for c in nb.cells if c["cell_type"] == "markdown"]
    assert len(markdown_cells) == 4  # 4 markdown cells in SAMPLE_CELLS


def test_build_notebook_code_cells():
    """Code cells must be created with correct source."""
    nb = build_notebook(SAMPLE_CELLS)
    code_cells = [c for c in nb.cells if c["cell_type"] == "code"]
    assert len(code_cells) == 6  # 6 code cells in SAMPLE_CELLS


def test_build_notebook_cell_sources():
    """Cell sources must match input data."""
    nb = build_notebook(SAMPLE_CELLS)
    for i, (cell, expected) in enumerate(zip(nb.cells, SAMPLE_CELLS)):
        assert cell.source == expected["source"], f"Cell {i} source mismatch"


def test_build_notebook_empty_cells():
    """build_notebook() with empty cells list must return valid empty notebook."""
    nb = build_notebook([])
    assert isinstance(nb, nbformat.NotebookNode)
    assert len(nb.cells) == 0
    nbformat.validate(nb)


# ─────────────────────────────────────────────────────────────────────────────
# generate_notebook() tests (mocked Gemini)
# ─────────────────────────────────────────────────────────────────────────────


def _mock_gemini_response():
    """Create a mock Gemini response with .text attribute."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(SAMPLE_GEMINI_RESPONSE)
    return mock_response


@pytest.mark.asyncio
async def test_generate_notebook_returns_tuple():
    """generate_notebook() must return (NotebookNode, list[str])."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response()
        mock_genai.Client.return_value = mock_client

        progress_calls = []

        async def mock_progress(msg: str) -> None:
            progress_calls.append(msg)

        paper = {
            "title": "Attention Is All You Need",
            "abstract": "We propose the Transformer architecture...",
            "full_text": "Paper text here...",
        }

        nb, bullets = await generate_notebook(paper, "AIzaTest123", mock_progress)

    assert isinstance(nb, nbformat.NotebookNode)
    assert isinstance(bullets, list)


@pytest.mark.asyncio
async def test_generate_notebook_calls_progress():
    """generate_notebook() must call progress callback at least once."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response()
        mock_genai.Client.return_value = mock_client

        progress_calls = []

        async def mock_progress(msg: str) -> None:
            progress_calls.append(msg)

        paper = {"title": "Test Paper", "abstract": "Test abstract", "full_text": "..."}
        await generate_notebook(paper, "AIzaTest", mock_progress)

    assert len(progress_calls) > 0


@pytest.mark.asyncio
async def test_generate_notebook_summary_bullets():
    """generate_notebook() must return exactly 3 summary bullets from Gemini response."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response()
        mock_genai.Client.return_value = mock_client

        async def mock_progress(msg: str) -> None:
            pass

        paper = {"title": "Test", "abstract": "Abstract", "full_text": "..."}
        nb, bullets = await generate_notebook(paper, "AIzaTest", mock_progress)

    assert len(bullets) == 3
    assert all(isinstance(b, str) for b in bullets)


@pytest.mark.asyncio
async def test_generate_notebook_passes_api_key():
    """generate_notebook() must pass the api_key to genai.Client constructor."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response()
        mock_genai.Client.return_value = mock_client

        async def mock_progress(msg: str) -> None:
            pass

        paper = {"title": "Test", "abstract": "Abstract", "full_text": "..."}
        await generate_notebook(paper, "AIzaRealKey123", mock_progress)

        mock_genai.Client.assert_called_once_with(api_key="AIzaRealKey123")


@pytest.mark.asyncio
async def test_generate_notebook_uses_gemini_flash():
    """generate_notebook() must use gemini-2.5-flash model."""
    with patch("notebook_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response()
        mock_genai.Client.return_value = mock_client

        async def mock_progress(msg: str) -> None:
            pass

        paper = {"title": "Test", "abstract": "Abstract", "full_text": "..."}
        await generate_notebook(paper, "AIzaTest", mock_progress)

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs.get("model") == "gemini-2.5-flash"
