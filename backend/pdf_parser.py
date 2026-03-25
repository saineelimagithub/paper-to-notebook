"""
PDF Parser — extracts structured content from research paper PDFs.
Uses PyMuPDF (fitz) for reliable text extraction including multi-column layouts.
"""
from __future__ import annotations

import re
from typing import Any

import fitz  # PyMuPDF


# Common section heading patterns found in academic papers
_SECTION_PATTERNS = re.compile(
    r"^(?:"
    r"\d+[\.\s]+[A-Z]|"                  # "1. Introduction" or "1 Introduction"
    r"(?:Abstract|Introduction|Related Work|Background|"
    r"Methodology|Method|Methods|Approach|"
    r"Experiments?|Experimental Results?|Results?|"
    r"Evaluation|Analysis|Discussion|"
    r"Conclusion|Conclusions?|Future Work|"
    r"Acknowledgements?|References?|Appendix)"
    r").*$",
    re.IGNORECASE,
)

_ABSTRACT_PATTERN = re.compile(r"^\s*abstract\s*$", re.IGNORECASE)


def _empty_result() -> dict:
    return {"title": "", "abstract": "", "sections": [], "full_text": ""}


def parse_pdf(pdf_bytes: bytes) -> dict:
    """
    Extract structured content from a research paper PDF.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        {
            "title": str,          # First large-font text on page 1
            "abstract": str,       # Text after "Abstract" heading
            "sections": [{"heading": str, "text": str}, ...],
            "full_text": str,      # Complete extracted text (all pages)
        }
    """
    if not pdf_bytes:
        return _empty_result()

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return _empty_result()

    if doc.page_count == 0:
        doc.close()
        return _empty_result()

    try:
        full_text = _extract_full_text(doc)
        title = _extract_title(doc)
        abstract, sections = _extract_structure(full_text)
    except Exception:
        doc.close()
        return _empty_result()

    doc.close()
    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "full_text": full_text,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _extract_full_text(doc: fitz.Document) -> str:
    """Concatenate plain text from all pages."""
    pages: list[str] = []
    for page in doc:
        try:
            pages.append(page.get_text("text"))
        except Exception:
            continue
    return "\n".join(pages)


def _extract_title(doc: fitz.Document) -> str:
    """
    Find the title on page 1: the text span with the largest font size.
    Falls back to the first bold text, then the first non-empty line.
    """
    page = doc[0]
    try:
        blocks: list[Any] = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    except Exception:
        # Fallback: first non-empty line of plain text
        plain = page.get_text("text").strip()
        return plain.split("\n")[0].strip() if plain else ""

    # Collect (font_size, text) for all spans on page 1
    candidates: list[tuple[float, str]] = []
    for block in blocks:
        if block.get("type") != 0:  # text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                if text:
                    candidates.append((size, text))

    if not candidates:
        # No spans found — use plain text first line
        plain = page.get_text("text").strip()
        return plain.split("\n")[0].strip() if plain else ""

    # Pick span(s) with the maximum font size
    max_size = max(c[0] for c in candidates)
    # Collect all spans at that size and merge them as a title
    title_parts = [text for size, text in candidates if size == max_size]
    title = " ".join(title_parts).strip()

    # If title is unreasonably short (e.g., a single letter or number), try the
    # second largest size
    if len(title) < 4 and len(candidates) > 1:
        sorted_sizes = sorted({c[0] for c in candidates}, reverse=True)
        for alt_size in sorted_sizes[1:]:
            alt_parts = [text for size, text in candidates if size == alt_size]
            alt_title = " ".join(alt_parts).strip()
            if len(alt_title) >= 4:
                title = alt_title
                break

    return title


def _is_section_heading(line: str) -> bool:
    """Return True if a line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return False
    # Matches common section patterns
    if _SECTION_PATTERNS.match(stripped):
        return True
    # ALL CAPS line (not a single word like "I" or a number)
    if stripped.isupper() and len(stripped) > 3:
        return True
    # Title Case short line that is not a sentence
    words = stripped.split()
    if (
        2 <= len(words) <= 6
        and all(w[0].isupper() for w in words if w.isalpha())
        and not stripped.endswith(".")
    ):
        return True
    return False


def _extract_structure(full_text: str) -> tuple[str, list[dict]]:
    """
    Parse full_text into abstract and sections.

    Returns:
        (abstract_text, [{"heading": str, "text": str}, ...])
    """
    lines = full_text.split("\n")
    abstract = ""
    sections: list[dict] = []

    in_abstract = False
    abstract_lines: list[str] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Detect "Abstract" heading
        if _ABSTRACT_PATTERN.match(stripped):
            in_abstract = True
            current_heading = None
            continue

        # Detect any section heading
        if _is_section_heading(stripped):
            # Save previous section
            if current_heading is not None:
                sections.append(
                    {"heading": current_heading, "text": " ".join(current_body).strip()}
                )
                current_body = []

            # Finish abstract if we were collecting it
            if in_abstract and not abstract:
                abstract = " ".join(abstract_lines).strip()
            in_abstract = False

            # Skip "Abstract" heading itself from sections list
            if _ABSTRACT_PATTERN.match(stripped):
                continue

            current_heading = stripped
            continue

        # Collect abstract body
        if in_abstract:
            abstract_lines.append(stripped)
            continue

        # Collect section body
        if current_heading is not None:
            current_body.append(stripped)

    # Flush last section
    if current_heading is not None:
        sections.append({"heading": current_heading, "text": " ".join(current_body).strip()})

    # If abstract was never ended by a heading
    if in_abstract and not abstract:
        abstract = " ".join(abstract_lines).strip()

    return abstract, sections
