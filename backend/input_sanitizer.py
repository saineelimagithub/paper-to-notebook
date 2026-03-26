"""
Input Sanitizer — strips control characters and neutralizes prompt injection
patterns in PDF-extracted text before sending to Gemini.
"""
from __future__ import annotations

import re

# Unicode control characters to strip
_CONTROL_CHARS = re.compile(
    "["
    "\u200b-\u200f"  # Zero-width and directional markers
    "\u202a-\u202e"  # Bidi embedding/override
    "\u2060-\u2064"  # Word joiner, invisible operators
    "\ufeff"          # BOM / zero-width no-break space
    "]"
)

# Prompt injection patterns (case-insensitive)
_INJECTION_PATTERNS = re.compile(
    r"^.*("
    r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions"
    r"|you\s+are\s+now"
    r"|new\s+instructions\s*:"
    r"|^system\s*:"
    r"|^admin\s*:"
    r"|disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts)"
    r"|override\s+(?:all\s+)?(?:safety|security)"
    r"|forget\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)"
    r").*$",
    re.IGNORECASE | re.MULTILINE,
)

MAX_FULL_TEXT = 12_000


def sanitize_paper_text(paper: dict) -> dict:
    """
    Sanitize extracted paper text before sending to Gemini.

    - Strips Unicode control characters
    - Neutralizes prompt injection patterns by prefixing with [USER TEXT]:
    - Truncates full_text to 12000 characters

    Returns a new dict (does not mutate the input).
    """
    result = dict(paper)

    # Strip control chars from all text fields
    for key in ("title", "abstract", "full_text"):
        if key in result and isinstance(result[key], str):
            result[key] = _CONTROL_CHARS.sub("", result[key])

    # Sanitize sections
    if "sections" in result:
        result["sections"] = [
            {
                "heading": _CONTROL_CHARS.sub("", s.get("heading", "")),
                "text": _CONTROL_CHARS.sub("", s.get("text", "")),
            }
            for s in result.get("sections", [])
        ]

    # Neutralize prompt injection in full_text
    if "full_text" in result:
        result["full_text"] = _neutralize_injections(result["full_text"])

    # Truncate
    if "full_text" in result and len(result["full_text"]) > MAX_FULL_TEXT:
        result["full_text"] = result["full_text"][:MAX_FULL_TEXT]

    return result


def _neutralize_injections(text: str) -> str:
    """Prefix lines containing prompt injection patterns with [USER TEXT]:"""
    lines = text.split("\n")
    sanitized = []
    for line in lines:
        if _INJECTION_PATTERNS.match(line):
            sanitized.append(f"[USER TEXT]: {line}")
        else:
            sanitized.append(line)
    return "\n".join(sanitized)
