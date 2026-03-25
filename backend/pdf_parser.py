"""
PDF Parser — extracts structured content from research paper PDFs.
Uses PyMuPDF (fitz) for reliable text extraction including multi-column layouts.
Implemented fully in Task 2.
"""
from __future__ import annotations


def parse_pdf(pdf_bytes: bytes) -> dict:
    """
    Extract structured content from a research paper PDF.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        {
            "title": str,
            "abstract": str,
            "sections": [{"heading": str, "text": str}, ...],
            "full_text": str,
        }
    """
    raise NotImplementedError("Implemented in Task 2")
