"""
Tests for pdf_parser.parse_pdf()
Run: cd backend && python -m pytest ../tests/backend/test_pdf_parser.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import fitz  # PyMuPDF
import pytest
from pdf_parser import parse_pdf, _is_section_heading, _extract_structure


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


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


def make_single_page_pdf(text: str = "Hello World", fontsize: float = 12) -> bytes:
    """Create a single-page PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=fontsize, color=(0, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_empty_page_pdf() -> bytes:
    """Create a PDF with one blank page (no text)."""
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_multi_section_pdf() -> bytes:
    """Create a PDF with multiple named sections to test structure extraction."""
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 60), "A Great Title", fontsize=24, color=(0, 0, 0))
    page.insert_text((72, 110), "Abstract", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 130), "This is the abstract text about our work.", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 180), "1. Introduction", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 200), "We study the problem of classification.", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 250), "2. Related Work", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 270), "Previous studies have shown improvements.", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 320), "3. Methodology", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 340), "We propose a novel framework.", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 390), "4. Experiments", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 410), "We ran extensive experiments.", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 460), "5. Conclusion", fontsize=12, color=(0, 0, 0))
    page.insert_text((72, 480), "We demonstrated effectiveness.", fontsize=10, color=(0, 0, 0))

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Basic parse_pdf() tests (existing, preserved)
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


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Empty / edge case tests
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_page_returns_empty_result():
    """A PDF with a blank page (no text) should return empty strings."""
    result = parse_pdf(make_empty_page_pdf())
    assert result["full_text"].strip() == ""
    assert result["abstract"] == ""
    assert result["sections"] == []


def test_none_bytes_returns_empty_result():
    """parse_pdf(b'') must return the empty result dict."""
    result = parse_pdf(b"")
    assert result["title"] == ""
    assert result["abstract"] == ""
    assert result["full_text"] == ""
    assert result["sections"] == []


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Title extraction
# ─────────────────────────────────────────────────────────────────────────────


def test_title_extracted_by_largest_font():
    """Title should be the text with the largest font size on page 1."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Small Header", fontsize=10, color=(0, 0, 0))
    page.insert_text((72, 140), "Big Title Here", fontsize=28, color=(0, 0, 0))
    page.insert_text((72, 200), "Subtitle Text", fontsize=14, color=(0, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()

    result = parse_pdf(pdf_bytes)
    assert "Big Title Here" in result["title"]


def test_single_page_pdf_has_title():
    """A single-page PDF should extract a title."""
    result = parse_pdf(make_single_page_pdf("My Research Paper", fontsize=18))
    assert "My Research Paper" in result["title"]


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Multi-page content
# ─────────────────────────────────────────────────────────────────────────────


def test_multi_page_full_text_includes_all_pages():
    """full_text must include content from all pages."""
    pdf_bytes = make_minimal_pdf()
    result = parse_pdf(pdf_bytes)
    # Page 1 has "Introduction", page 2 has "Method"
    assert "Introduction" in result["full_text"]
    assert "Method" in result["full_text"]


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Abstract extraction
# ─────────────────────────────────────────────────────────────────────────────


def test_abstract_extracted_from_pdf():
    """Abstract text should be extracted when 'Abstract' heading is present."""
    result = parse_pdf(make_multi_section_pdf())
    assert "abstract" in result["abstract"].lower() or len(result["abstract"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Section heading detection (_is_section_heading)
# ─────────────────────────────────────────────────────────────────────────────


def test_section_heading_numbered():
    """Numbered headings like '1. Introduction' should be detected."""
    assert _is_section_heading("1. Introduction")
    assert _is_section_heading("2 Related Work")
    assert _is_section_heading("3. Methodology")


def test_section_heading_named():
    """Named headings like 'Introduction', 'Conclusion' should be detected."""
    assert _is_section_heading("Introduction")
    assert _is_section_heading("Conclusion")
    assert _is_section_heading("Related Work")
    assert _is_section_heading("Experiments")


def test_section_heading_all_caps():
    """ALL CAPS headings should be detected."""
    assert _is_section_heading("INTRODUCTION")
    assert _is_section_heading("RELATED WORK")


def test_section_heading_rejects_regular_text():
    """Regular body text should not be detected as a section heading."""
    assert not _is_section_heading("This is a regular sentence.")
    assert not _is_section_heading("")
    assert not _is_section_heading("   ")


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Structure extraction (_extract_structure)
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_structure_finds_abstract():
    """_extract_structure should extract abstract text after 'Abstract' heading."""
    text = "Abstract\nThis is the abstract content.\n1. Introduction\nIntro text."
    abstract, sections = _extract_structure(text)
    assert "abstract content" in abstract


def test_extract_structure_finds_sections():
    """_extract_structure should extract sections with headings."""
    text = "Abstract\nSome abstract.\n1. Introduction\nIntro text here.\n2. Methods\nMethod details."
    abstract, sections = _extract_structure(text)
    assert len(sections) >= 2
    headings = [s["heading"] for s in sections]
    assert any("Introduction" in h for h in headings)
    assert any("Methods" in h or "Method" in h for h in headings)


def test_extract_structure_empty_text():
    """_extract_structure with empty string should return empty results."""
    abstract, sections = _extract_structure("")
    assert abstract == ""
    assert sections == []


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Multi-section PDF end-to-end
# ─────────────────────────────────────────────────────────────────────────────


def test_multi_section_pdf_extracts_multiple_sections():
    """A PDF with multiple numbered sections should have multiple sections extracted."""
    result = parse_pdf(make_multi_section_pdf())
    assert len(result["sections"]) >= 3


def test_multi_section_pdf_title():
    """A multi-section PDF should extract the large-font title."""
    result = parse_pdf(make_multi_section_pdf())
    assert "Great Title" in result["title"]
