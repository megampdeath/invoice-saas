"""Tests for mock + pdf_text extraction providers (§18)."""
import os
import tempfile

from app.extraction.mock_provider import MockExtractionProvider
from app.extraction.pdf_text_provider import TextPdfExtractionProvider


def test_mock_provider_returns_deterministic_fields():
    p = MockExtractionProvider()
    r = p.extract("ignore.pdf", "application/pdf")
    assert r.provider == "mock"
    assert r.fields["invoice_number"].value == "FA-2026-001"
    assert r.fields["total_amount"].value == "1200.00"
    assert 0.0 <= r.fields["total_amount"].confidence <= 1.0


def test_pdf_text_provider_extracts_from_real_pdf():
    try:
        from pypdf import PdfWriter
    except Exception:
        # pypdf not installed in this env; skip
        import pytest
        pytest.skip("pypdf not installed")
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        w.write(tmp.name)
        path = tmp.name
    try:
        r = TextPdfExtractionProvider().extract(path, "application/pdf")
        assert r.provider == "pdf_text"
        # blank page -> no fields, but no crash
        assert isinstance(r.fields, dict)
    finally:
        os.unlink(path)


def test_pdf_text_provider_parses_amounts_from_text(tmp_path):
    # Build a tiny PDF with text via reportlab if available
    try:
        from reportlab.pdfgen import canvas
    except Exception:
        import pytest
        pytest.skip("reportlab not installed")
    path = str(tmp_path / "inv.pdf")
    c = canvas.Canvas(path)
    c.drawString(72, 720, "Invoice No: FA-2026-009")
    c.drawString(72, 700, "Total: 1200.00")
    c.drawString(72, 680, "Date: 23/06/2026")
    c.save()
    r = TextPdfExtractionProvider().extract(path, "application/pdf")
    assert r.fields.get("invoice_number").value == "FA-2026-009"
    assert r.fields.get("total_amount").value == "1200.00"