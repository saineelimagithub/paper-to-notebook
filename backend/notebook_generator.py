"""
Notebook Generator — uses GPT-5.4 to analyze a research paper and generates
a production-quality Google Colab notebook via nbformat.
Implemented fully in Task 3.
"""
from __future__ import annotations

from typing import Callable, Awaitable


async def generate_notebook(
    paper: dict,
    api_key: str,
    progress: Callable[[str], Awaitable[None]],
) -> tuple:
    """
    Analyze the paper with GPT-5.4 and build a research-grade .ipynb notebook.

    Args:
        paper:    Parsed paper dict from pdf_parser.parse_pdf()
        api_key:  User's OpenAI API key (forwarded per-request, never stored)
        progress: Async callback to push progress messages to the SSE stream

    Returns:
        (NotebookNode, summary_bullets: list[str])
    """
    raise NotImplementedError("Implemented in Task 3")
