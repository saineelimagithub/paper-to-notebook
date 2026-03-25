"""
Tests for pdf_parser.parse_pdf()
Run: cd backend && python -m pytest ../tests/backend/test_pdf_parser.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import fitz  # PyMuPDF
import pytest
from pdf_parser import parse_pdf


def make_minimal_pdf() -> bytes:
    """Create a minimal in-memory research-paper-like PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()

    # Insert title with larger font
    page.insert_text((72, 100), "Deep Learning for Everything", fontsize=20, color=(0, 0, 0))

    # Insert abstract heading + body
    page.insert_text((72, 150), "Abstract", fontsize=12, color=(0, 0, 0))
    page.insert_text(
        (72, 170),
        "This paper presents a novel approach to deep learning.",
        fontsize=10,
        color=(0, 0, 0),
    )

    # Insert section
    page.insert_text((72, 220), "Introduction", fontsize=12, color=(0, 0, 0))
    page.insert_text(
        (72, 240),
        "We introduce our method here.",
        fontsize=10,
        color=(0, 0, 0),
    )

    # Add a second page
    page2 = doc.new_page()
    page2.insert_text((72, 100), "Method", fontsize=12, color=(0, 0, 0))
    page2.insert_text((72, 120), "Our method works as follows.", fontsize=10, color=(0, 0, 0))

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────


def test_parse_pdf_returns_required_keys():
    """parse_pdf() must return a dict with all required keys."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert isinstance(result, dict)
    for key in ("title", "abstract", "sections", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_title_is_nonempty_string():
    """title must be a non-empty string."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert isinstance(result["title"], str)
    assert len(result["title"]) > 0


def test_full_text_is_nonempty_string():
    """full_text must concatenate all pages — non-empty for a real PDF."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert isinstance(result["full_text"], str)
    assert len(result["full_text"]) > 0


def test_sections_is_list():
    """sections must be a list (may be empty for minimal PDF)."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert isinstance(result["sections"], list)


def test_abstract_is_string():
    """abstract must be a string (may be empty for minimal PDF)."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert isinstance(result["abstract"], str)


def test_handles_corrupt_bytes_gracefully():
    """parse_pdf() must not raise on corrupt/empty bytes — return empty-string fields."""
    result = parse_pdf(b"not a pdf at all")
    assert isinstance(result, dict)
    for key in ("title", "abstract", "full_text"):
        assert isinstance(result[key], str)
    assert isinstance(result["sections"], list)


def test_handles_empty_bytes_gracefully():
    """parse_pdf() must not raise on empty bytes."""
    result = parse_pdf(b"")
    assert isinstance(result, dict)
    for key in ("title", "abstract", "full_text"):
        assert isinstance(result[key], str)
    assert isinstance(result["sections"], list)


def test_full_text_contains_content():
    """full_text should contain text from the PDF."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    assert "Deep Learning" in result["full_text"] or "Introduction" in result["full_text"]


def test_sections_have_correct_structure():
    """Each section in sections must have 'heading' and 'text' keys."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    for section in result["sections"]:
        assert "heading" in section, f"Section missing 'heading': {section}"
        assert "text" in section, f"Section missing 'text': {section}"
        assert isinstance(section["heading"], str)
        assert isinstance(section["text"], str)
