"""
Safe Error Handler — maps exceptions to generic user-facing messages.
Full details are logged server-side only.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("paper_notebook")

_AUTH_PATTERNS = re.compile(
    r"(401|403|unauthorized|forbidden|invalid.*(?:api|key)|permission.denied)",
    re.IGNORECASE,
)

_PDF_PATTERNS = re.compile(
    r"(fitz|pymupdf|cannot open.*(?:document|file)|pdf|parse.*error|format.error)",
    re.IGNORECASE,
)


def safe_error_message(exc: Exception) -> str:
    """
    Return a generic, safe error message for the user.
    Logs the full exception server-side.

    Categories:
    - Auth errors → "Invalid API key."
    - PDF errors → "PDF could not be parsed."
    - Everything else → "Generation failed. Please try again."
    """
    raw = str(exc)

    # Log full details server-side
    logger.error("Generation error: %s: %s", type(exc).__name__, raw, exc_info=True)

    # Classify
    if _AUTH_PATTERNS.search(raw):
        return "Invalid API key."

    if _PDF_PATTERNS.search(raw):
        return "PDF could not be parsed."

    return "Generation failed. Please try again."
